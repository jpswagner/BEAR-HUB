# PORT.py — Bactopia UI Local (PORT via Nextflow)
# ----------------------------------------------------------------------
# Usage: as a page within BEAR-HUB (pages/PORT.py) or as standalone script.
# Requirements: streamlit>=1.30; Nextflow + (Docker/Apptainer); PORT cloned
# ----------------------------------------------------------------------

"""
PORT Interface.

This module provides a UI for running PORT (Plasmid Outbreak Research Tool).
It supports:
1.  **Input Modes**: Running on raw Nanopore FASTQs or existing Bactopia assemblies.
2.  **Assembly Management**: Automatically creating a `port_assemblies` directory
    symlinked/copied from Bactopia output.
3.  **Configuration**: Setting assemblers, read types, and resource limits.
4.  **Execution**: Asynchronous running of the PORT Nextflow pipeline.

NOTE: This module is under active development. Some features may be incomplete.
"""

import os
import shlex
import time
import pathlib
import shutil
import gzip
from typing import List

import streamlit as st

# Import utility module from parent directory (or same directory if running from root)
try:
    import utils
except ImportError:
    import sys
    sys.path.append(str(pathlib.Path(__file__).parent.parent))
    import utils

utils.bootstrap_bear_env_from_file()

# ============================= Config geral =============================
st.set_page_config(page_title="BEAR-HUB", page_icon="🐻", layout="wide")

APP_ROOT = pathlib.Path(__file__).resolve().parent

# Project root discovery
if (APP_ROOT / "static").is_dir():
    PROJECT_ROOT = APP_ROOT
elif (APP_ROOT.parent / "static").is_dir():
    PROJECT_ROOT = APP_ROOT.parent
else:
    PROJECT_ROOT = APP_ROOT  # fallback

APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
DEFAULT_BACTOPIA_OUTDIR = str((pathlib.Path.cwd() / "bactopia_out").resolve())
DEFAULT_PORT_OUTDIR = str((pathlib.Path.cwd() / "port_out").resolve())

# ── Session state defaults ────────────────────────────────────────────────────
utils.init_session_state({
    "port_running": False,
    "port_input_mode": "Bactopia Assemblies (per sample)",
    "port_assemblies_path": "",
    "port_selected_samples": [],
    "port_last_bactopia_dir": "",
    "port_bactopia_samples": {},
})

# ============================= Development banner =============================

st.warning(
    "**PORT is under active development.** Some features may be incomplete or not work "
    "as expected. Please check the [GitHub repository](https://github.com/jpswagner/BEAR-HUB) "
    "for the latest status.",
    icon="⚠️",
)

st.title("PORT — Nanopore Assembly & Plasmid Typing")
st.markdown(
    """
This page integrates **PORT** (Plasmid Outbreak Research Tool) with BEAR-HUB:

- Run PORT with **Nanopore FASTQs** (`--input_dir`)
- Run PORT using **Bactopia assemblies per sample** (`--assemblies`),
  automatically building the `port_assemblies/` folder from `bactopia_out`.
"""
)

# ============================= Helper functions =============================

def extract_sample_id_from_filename(path: pathlib.Path) -> str:
    """Extract sample ID from a FASTA filename (strips extensions)."""
    name = path.name
    for ext in (".fa.gz", ".fna.gz", ".fasta.gz", ".fa", ".fna", ".fasta"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    if "." in name:
        name = name.split(".", 1)[0]
    return name


def scan_bactopia_assemblies(bactopia_run_dir: str) -> dict:
    """
    Scan a Bactopia output directory for assembly files.

    Returns:
        dict mapping sample_id → list of FASTA file paths.
    """
    run_path = pathlib.Path(bactopia_run_dir).expanduser().resolve()
    if not run_path.exists():
        return {}

    sample_map: dict = {}
    patterns = ("*.fa", "*.fna", "*.fasta", "*.fa.gz", "*.fna.gz", "*.fasta.gz")
    for pattern in patterns:
        for f in run_path.rglob(pattern):
            if "port_assemblies" in f.parts:
                continue
            sid = extract_sample_id_from_filename(f)
            sample_map.setdefault(sid, []).append(f)
    return sample_map


def _base_name_without_ext(path: pathlib.Path) -> str:
    """Return filename without any FASTA extension."""
    name = path.name
    for ext in (".fa.gz", ".fna.gz", ".fasta.gz", ".fa", ".fna", ".fasta"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return path.stem


def build_port_assemblies_from_sample_map(
    bactopia_run_dir: str, sample_map: dict, selected_samples: list
) -> tuple[pathlib.Path, int]:
    """
    Prepare the `port_assemblies` directory from selected Bactopia samples.

    Creates symlinks for uncompressed FASTA files and decompresses .gz files.

    Returns:
        (target_dir, count_created)
    """
    run_path = pathlib.Path(bactopia_run_dir).expanduser().resolve()
    target = run_path / "port_assemblies"
    target.mkdir(parents=True, exist_ok=True)

    # Clear existing contents
    for item in list(target.iterdir()):
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
        except Exception:
            pass

    created = 0
    for sid in selected_samples:
        for f in sample_map.get(sid, []):
            core = _base_name_without_ext(f)
            out_path = target / f"{sid}__{core}.fasta"
            if out_path.exists():
                continue

            src_str = str(f)
            lower = src_str.lower()

            if lower.endswith((".fa.gz", ".fna.gz", ".fasta.gz")):
                try:
                    with gzip.open(src_str, "rb") as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    created += 1
                except Exception as e:
                    st.warning(f"Could not decompress {f.name}: {e}")
            elif lower.endswith((".fa", ".fna", ".fasta")):
                try:
                    os.symlink(f, out_path)
                    created += 1
                except Exception as e:
                    st.warning(f"Could not create symlink for {f.name}: {e}")

    return target, created


# ============================= General configuration =============================

st.subheader("General PORT configuration")

col_cfg1, col_cfg2 = st.columns([2, 1])

with col_cfg1:
    main_nf_path = st.text_input(
        "Path to PORT main.nf",
        value=st.session_state.get("port_main_nf", "/mnt/HD/PORT/PORT/main.nf"),
        key="port_main_nf",
        help="e.g. /mnt/HD/PORT/PORT/main.nf or a relative path.",
    ).strip()
    if not main_nf_path:
        main_nf_path = "main.nf"

    exec_mode = st.selectbox(
        "Execution environment",
        options=["Docker (default / standard profile)", "Conda (conda profile)"],
        index=0,
        key="port_exec_mode",
    )

    # --- Input type selection ---
    input_mode = st.radio(
        "Input type",
        options=["Nanopore FASTQs (raw reads)", "Bactopia Assemblies (per sample)"],
        index=1,
        key="port_input_mode",
    )

    input_dir = ""
    assemblies_dir = ""

    if input_mode.startswith("Nanopore"):
        input_dir = st.text_input(
            "FASTQ directory (Nanopore) — --input_dir",
            value=st.session_state.get("port_input_dir", "input"),
            key="port_input_dir",
            help="Directory passed to --input_dir (all FASTQ/FASTQ.GZ files).",
        ).strip()
    else:
        asm_state_key = "port_assemblies_path"
        assemblies_default = st.session_state.get(asm_state_key, "")

        assemblies_dir = st.text_input(
            "Assemblies directory for PORT — --assemblies",
            value=assemblies_default,
            help="Directory with .fasta files (the port_assemblies folder generated below).",
        ).strip()
        st.session_state[asm_state_key] = assemblies_dir

        with st.expander("Build 'port_assemblies' folder from Bactopia output", expanded=True):
            bactopia_run_dir = st.text_input(
                "Bactopia results folder (bactopia_out)",
                value=st.session_state.get("port_bactopia_outdir", DEFAULT_BACTOPIA_OUTDIR),
                key="port_bactopia_outdir",
                help="Root of bactopia_out. The app will search for FASTA files recursively, grouped by sample.",
            ).strip()

            sample_map: dict = {}
            if bactopia_run_dir:
                ok_path, _ = utils.validate_path(bactopia_run_dir)
                if not ok_path:
                    st.error("Invalid path for Bactopia results folder.")
                else:
                    last_dir = st.session_state.get("port_last_bactopia_dir")
                    if last_dir != bactopia_run_dir or not st.session_state.get("port_bactopia_samples"):
                        sample_map = scan_bactopia_assemblies(bactopia_run_dir)
                        st.session_state["port_last_bactopia_dir"] = bactopia_run_dir
                        st.session_state["port_bactopia_samples"] = sample_map
                    else:
                        sample_map = st.session_state["port_bactopia_samples"]

            if sample_map:
                total_samples = len(sample_map)
                total_files = sum(len(v) for v in sample_map.values())
                st.info(
                    f"Found **{total_samples} sample(s)** with "
                    f"**{total_files} FASTA/FA file(s)** (.fa/.fna/.fasta/.gz)."
                )

                sample_ids = sorted(sample_map.keys())
                default_sel = st.session_state.get("port_selected_samples") or sample_ids
                selected_samples = st.multiselect(
                    "Select samples for PORT input",
                    options=sample_ids,
                    default=default_sel,
                    key="port_selected_samples",
                    help="Sample IDs inferred from FASTA filenames.",
                )

                if st.button("Create / update 'port_assemblies' folder"):
                    if not selected_samples:
                        st.error("Select at least one sample.")
                    else:
                        target, created = build_port_assemblies_from_sample_map(
                            bactopia_run_dir, sample_map, selected_samples
                        )
                        st.session_state[asm_state_key] = str(target)
                        assemblies_dir = str(target)
                        st.success(
                            f"Folder **{target}** updated. "
                            f"Created **{created} .fasta file(s)** (decompressed or symlinked)."
                        )
            else:
                if bactopia_run_dir:
                    st.warning("No FASTA files (.fa/.fna/.fasta/.gz) found in this bactopia_out.")
                else:
                    st.info("Provide the bactopia_out folder path to detect samples.")

    # --- PORT output directory ---
    output_dir = st.text_input(
        "PORT output directory — --output_dir",
        value=st.session_state.get("port_outdir", DEFAULT_PORT_OUTDIR),
        key="port_outdir",
        help="PORT results will be written here.",
    ).strip()

    # --- Assembly parameters ---
    st.markdown("### Assembly parameters")

    assembler = st.selectbox(
        "Assembler (--assembler)",
        options=["autocycler", "dragonflye"],
        index=0,
        key="port_assembler",
        help="See PORT documentation for details.",
    )

    read_type = st.text_input(
        "Read type (--read_type)",
        value=st.session_state.get("port_read_type", "ont_r10"),
        key="port_read_type",
        help="e.g. ont_r9, ont_r10. Primarily used in Medaka polishing steps.",
    ).strip()

    medaka_model = st.text_input(
        "Medaka model (--medaka_model)",
        value=st.session_state.get("port_medaka_model", "r1041_e82_400bps_sup"),
        key="port_medaka_model",
        help="Medaka model for polishing (most relevant for dragonflye).",
    ).strip()

    st.markdown("### Nextflow global resources")

    c_res1, c_res2 = st.columns(2)
    with c_res1:
        max_cpus = st.number_input(
            "--max_cpus",
            min_value=1,
            max_value=min(os.cpu_count() or 64, 256),
            value=16,
            step=1,
            key="port_max_cpus",
        )
    with c_res2:
        max_memory = st.text_input(
            "--max_memory",
            value=st.session_state.get("port_max_memory", "64.GB"),
            key="port_max_memory",
            help="e.g. 32.GB, 64.GB, 128.GB",
        ).strip()

with col_cfg2:
    st.subheader("Execution & Log")

    status_box_port = st.empty()

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        start_port = st.button(
            "▶️ Start PORT",
            key="btn_port_start",
            disabled=True,  # Coming Soon — PORT integration is under development
            help="PORT execution is coming soon. The module is still under development.",
        )
    with c_btn2:
        stop_port = st.button(
            "⏹️ Stop",
            key="btn_port_stop",
            disabled=not st.session_state.get("port_running", False),
        )

    st.info("Run button is disabled while PORT integration is in development.")

    if stop_port:
        utils.request_stop_ns("port")
        status_box_port.warning("Stop requested…")

# ============================= Nextflow command preview =============================
cmd_parts = ["nextflow", "run", main_nf_path]

if input_mode.startswith("Nanopore"):
    if input_dir:
        cmd_parts += ["--input_dir", input_dir]
else:
    if assemblies_dir:
        cmd_parts += ["--assemblies", assemblies_dir]

if output_dir:
    cmd_parts += ["--output_dir", output_dir]

cmd_parts += ["--assembler", assembler]

if read_type:
    cmd_parts += ["--read_type", read_type]
if medaka_model:
    cmd_parts += ["--medaka_model", medaka_model]

if exec_mode.startswith("Conda"):
    cmd_parts += ["-profile", "conda"]
    conda_env = st.text_input(
        "Conda environment name (--conda_env, optional)",
        value=st.session_state.get("port_conda_env", ""),
        key="port_conda_env",
        help="If empty, the pipeline's default conda environment is used.",
    ).strip()
    if conda_env:
        cmd_parts += ["--conda_env", conda_env]

if max_cpus:
    cmd_parts += ["--max_cpus", str(max_cpus)]
if max_memory:
    cmd_parts += ["--max_memory", max_memory]

cmd_parts.append("-resume")

cmd_preview = " ".join(shlex.quote(x) for x in cmd_parts)

st.markdown("#### Nextflow command preview")
st.code(cmd_preview, language="bash")

# ============================= Async execution (placeholder) =============================
if start_port:
    # This branch is unreachable while the button is disabled=True,
    # but is kept ready for when PORT is fully integrated.
    if not utils.nextflow_available():
        status_box_port.error("Nextflow not found in PATH.")
    elif input_mode.startswith("Nanopore") and not input_dir:
        status_box_port.error("Provide the FASTQ directory for --input_dir.")
    elif not input_mode.startswith("Nanopore") and not assemblies_dir:
        status_box_port.error(
            "Provide the assemblies directory for --assemblies "
            "(or generate the port_assemblies folder first)."
        )
    else:
        ok_out, msg_out = utils.validate_outdir(output_dir or "")
        if not ok_out:
            status_box_port.error(f"Invalid output directory: {msg_out}")
        else:
            stdbuf = shutil.which("stdbuf")
            full_cmd = cmd_preview
            if stdbuf:
                full_cmd = f"{stdbuf} -oL -eL {cmd_preview}"
            status_box_port.info("Running PORT (async).")
            _run_id = utils.record_run_start("PORT", [], full_cmd)
            st.session_state["_port_run_id"] = _run_id
            utils.start_async_runner_ns(full_cmd, "port")

# ============================= Live log =============================
st.markdown("---")
st.subheader("Nextflow output (PORT)")

if st.session_state.get("port_running", False):
    utils.drain_log_queue_ns("port", tail_limit=500, max_pull=800)
    utils.render_nxf_progress_ns("port")
    utils.render_log_box_ns("port", height=520)
    finished = utils.check_status_and_finalize_ns("port", status_box_port)
    if finished:
        _run_id = st.session_state.pop("_port_run_id", None)
        if _run_id is not None:
            try:
                utils.record_run_finish(_run_id, True)
            except Exception:
                pass
    if not finished:
        time.sleep(0.3)
        utils._st_rerun()
else:
    utils.render_nxf_progress_ns("port")
    utils.render_log_box_ns("port", height=520)
