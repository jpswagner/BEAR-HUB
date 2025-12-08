# MERLIN.py — Species-specific Bactopia tools (via --wf)
# ---------------------------------------------------------------
# Standalone usage:
#   streamlit run MERLIN.py
#
# Within BEAR-HUB, this file is used as an additional page.
# ---------------------------------------------------------------

"""
Merlin Interface.

This module provides a UI for running species-specific Bactopia tools (Merlin).
It organizes tools by genus/species (e.g., E. coli, Salmonella, Staphylococcus)
and allows users to select and run them on processed samples.

Key features:
1.  **Genus grouping**: Tools are grouped by target organism.
2.  **Sequential Execution**: Multiple selected tools are executed sequentially.
3.  **Sample Selection**: Users can choose specific samples from a Bactopia run.
4.  **Async Runner**: Background execution with real-time logging.
"""

import os
import shlex
import time
import pathlib
import shutil
import hashlib
from typing import List

import streamlit as st
import streamlit.components.v1 as components

# Import utility module from parent directory (or same directory if running from root)
try:
    import utils
except ImportError:
    import sys
    sys.path.append(str(pathlib.Path(__file__).parent.parent))
    import utils

# ============================= General config =============================
st.set_page_config(
    page_title="Bactopia — Species-specific tools | BEAR-HUB",
    page_icon="🐻",
    layout="wide",
)

APP_ROOT = pathlib.Path(__file__).resolve().parent
PAGES_DIR = APP_ROOT / "pages"
PAGE_BACTOPIA = PAGES_DIR / "BACTOPIA.py"
PAGE_TOOLS = PAGES_DIR / "BACTOPIA-TOOLS.py"
PAGE_MERLIN = PAGES_DIR / "MERLIN.py"
PAGE_PORT = PAGES_DIR / "PORT.py"

# Project root discovery
if (APP_ROOT / "static").is_dir():
    PROJECT_ROOT = APP_ROOT
elif (APP_ROOT.parent / "static").is_dir():
    PROJECT_ROOT = APP_ROOT.parent
else:
    PROJECT_ROOT = APP_ROOT  # fallback

APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
# Aligned with BEAR-HUB: ~/BEAR_DATA/bactopia_out
DEFAULT_OUTDIR = str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").resolve())

# ===================== Nextflow via Bactopia conda env =====================

# Try to load .bear-hub.env early
utils.bootstrap_bear_env_from_file()

BACTOPIA_ENV_PREFIX = os.environ.get("BACTOPIA_ENV_PREFIX")

def have_tool(name: str) -> bool:
    """Check if a tool is in PATH."""
    return utils.which(name) is not None

# ============================= Help (popovers) =============================

HELP: dict[str, str] = {}

HELP["samples"] = """
### Sample selection

- The list is inferred from the **folders** within `--bactopia` (one folder per sample).
- The app automatically generates an `--include` file with the selected samples.
"""

HELP["general"] = """
### General Nextflow/Bactopia parameters

- **`-profile`**  
  Execution environment. Typical values:
  - `docker` (Docker containers),
  - `singularity` (Apptainer),
  - `standard` (no containers).

- **`--max_cpus`**  
  Global thread limit for the Nextflow scheduler (not per task).

- **`--max_memory`**  
  Global memory ceiling, e.g. `64.GB`. Tasks that need more will wait in queue.

- **`-resume`**  
  Reuses completed steps via Nextflow cache. Recommended to keep **on**.

- **`Extras`**  
  Free-form field for additional flags:
  - extra Nextflow options (e.g. `-with-report report.html`)
  - extra Bactopia options.
"""

HELP["species"] = """
### Species-specific tools

- Each tool is a Bactopia `--wf` workflow tailored for a genus/species.
- Sample selection is based on the `--bactopia` directory (one folder per sample).
- You can tick multiple tools; they will be executed **sequentially**,
  each as its own:

  `nextflow run bactopia/bactopia --wf <tool> ...`
"""


def help_popover(label: str, text: str):
    """Show help in a popover."""
    with st.popover(label):
        st.markdown(text)


def help_header(title_md: str, help_key: str, ratio=(4, 1)):
    """Render a header with a help button."""
    c1, c2 = st.columns(ratio)
    with c1:
        st.markdown(title_md)
    with c2:
        help_popover("❓ Help", HELP[help_key])

# ============================= Bactopia helpers =============================

def discover_samples_from_outdir(outdir: str) -> List[str]:
    """
    Discover sample folders in the Bactopia output directory.

    Args:
        outdir (str): Path to Bactopia output.

    Returns:
        List[str]: Detected sample names.
    """
    p = pathlib.Path(outdir)
    if not p.exists() or not p.is_dir():
        return []
    samples_strict: List[str] = []
    candidates: List[str] = []

    for child in sorted(p.iterdir(), key=lambda x: x.name):
        if not child.is_dir():
            continue
        # Ignore administrative directories
        if child.name.startswith("bactopia-") or child.name in {"bactopia-runs", "work"}:
            continue
        candidates.append(child.name)
        if (child / "main").exists() or (child / "tools").exists():
            samples_strict.append(child.name)

    if samples_strict:
        return samples_strict
    return candidates


def _guess_bt_root_default() -> str:
    """
    Guess the default Bactopia results directory.

    Returns:
        str: Detected path or default fallback.
    """
    candidates: list[pathlib.Path] = []

    global_outdir = st.session_state.get("outdir")
    if global_outdir:
        base = pathlib.Path(global_outdir).expanduser()
        candidates.append(base)
        candidates.append(base / "bactopia_out")

    # Local projects
    candidates.append(PROJECT_ROOT / "bactopia_out")
    candidates.append(APP_ROOT / "bactopia_out")

    # Default fallback
    candidates.append(pathlib.Path.home() / "BEAR_DATA" / "bactopia_out")

    for cand in candidates:
        try:
            cand = cand.expanduser().resolve()
            if cand.exists() and cand.is_dir():
                if discover_samples_from_outdir(str(cand)):
                    return str(cand)
        except Exception:
            pass

    # If nothing worked, still return the last fallback
    return str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").expanduser().resolve())


def write_include_file(outdir: str, samples: List[str]) -> str:
    """
    Create a temporary include file for Nextflow.

    Args:
        outdir (str): Base output directory.
        samples (List[str]): List of sample names.

    Returns:
        str: Path to the generated include file.
    """
    utils.ensure_state_dir()
    fname = APP_STATE_DIR / f"include_{hashlib.md5((outdir + '|' + ';'.join(samples)).encode()).hexdigest()[:10]}.txt"
    with open(fname, "w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(s + "\n")
    return str(fname)


def bt_nextflow_cmd(
    tool: str,
    outdir: str,
    include_file: str,
    profile: str,
    threads: int | None = None,
    memory_gb: int | None = None,
    resume: bool = True,
    extra: List[str] | None = None,
) -> str:
    """
    Build the Nextflow command for a species workflow.

    Args:
        tool (str): Tool/Workflow name (e.g., 'ectyper').
        outdir (str): Bactopia output directory.
        include_file (str): Path to include file.
        profile (str): Nextflow profile.
        threads (int | None): Max CPUs.
        memory_gb (int | None): Max memory in GB.
        resume (bool): Whether to resume.
        extra (List[str] | None): Additional args.

    Returns:
        str: The full shell command.
    """
    nf_bin = utils.get_nextflow_bin()
    base = [
        nf_bin,
        "run",
        "bactopia/bactopia",
        "-profile",
        profile,
        "--wf",
        tool,
        "--bactopia",
        outdir,
        "--include",
        include_file,
    ]
    if threads and threads > 0:
        base += ["--max_cpus", str(threads)]
    if memory_gb and memory_gb > 0:
        base += ["--max_memory", f"{memory_gb}.GB"]
    if resume:
        base += ["-resume"]
    if extra:
        base += extra
    # Page-level "Extras" for species tools
    if (st.session_state.get("btsp_extra") or "").strip():
        base += shlex.split(st.session_state["btsp_extra"])
    return " ".join(shlex.quote(x) for x in base)

# ============================= Species-specific tools table =============================

SPECIES_TOOLS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Escherichia / Shigella",
        [
            ("ECTyper", "ectyper"),
            ("ShigaTyper", "shigatyper"),
            ("ShigEiFinder", "shigeifinder"),
        ],
    ),
    (
        "Haemophilus",
        [
            ("hicap", "hicap"),
            ("HpsuisSero", "hpsuissero"),
        ],
    ),
    (
        "Klebsiella",
        [
            ("Kleborate", "kleborate"),
        ],
    ),
    (
        "Legionella",
        [
            ("legsta", "legsta"),
        ],
    ),
    (
        "Listeria",
        [
            ("LisSero", "lissero"),
        ],
    ),
    (
        "Mycobacterium",
        [
            ("TBProfiler", "tbprofiler"),
        ],
    ),
    (
        "Neisseria",
        [
            ("meningotype", "meningotype"),
            ("ngmaster", "ngmaster"),
        ],
    ),
    (
        "Pseudomonas",
        [
            ("pasty", "pasty"),
        ],
    ),
    (
        "Salmonella",
        [
            ("SeqSero2", "seqsero2"),
            ("SISTR", "sistr"),
        ],
    ),
    (
        "Staphylococcus",
        [
            ("AgrVATE", "agrvate"),
            ("spaTyper", "spatyper"),
            ("staphopia-sccmec", "staphopia-sccmec"),
        ],
    ),
    (
        "Streptococcus",
        [
            ("emmtyper", "emmtyper"),
            ("pbptyper", "pbptyper"),
            ("SsuisSero", "ssuissero"),
        ],
    ),
]

# ============================= Page UI =============================

ICON_PATH = PROJECT_ROOT / "static" / "bear-hub-icon.png"
ICON_PATH_MERLIN = PROJECT_ROOT / "static" / "BEAR-MERLIN.png"

if ICON_PATH_MERLIN.is_file():
    st.image(str(ICON_PATH_MERLIN), width=500)
else:
    st.title("🧬 Bactopia — Species-specific tools")

# ------------------------- Run directory / samples -------------------------
st.subheader("Folder and sample selection")
help_popover("❓ Help", HELP["samples"])

bt_root_default = _guess_bt_root_default()

# Initialize bt_outdir only here so we don't fight with the widget
if "bt_outdir" not in st.session_state or not st.session_state["bt_outdir"]:
    st.session_state["bt_outdir"] = bt_root_default

bt_outdir = utils.path_picker(
    "Bactopia results directory",
    key="bt_outdir",
    mode="dir",
    start=bt_root_default,
    help="Directory containing Bactopia sample folders (one folder per sample).",
)

# If user clears the field, fall back to the computed default
bt_outdir = bt_outdir or bt_root_default
bt_outdir = str(pathlib.Path(bt_outdir).expanduser().resolve())
st.caption(f"Current directory: `{bt_outdir}`")

# Detect directory change to auto-select all samples
prev_bt_outdir = st.session_state.get("_prev_bt_outdir_merlin")
folder_changed = prev_bt_outdir is not None and prev_bt_outdir != bt_outdir
st.session_state["_prev_bt_outdir_merlin"] = bt_outdir

samples = discover_samples_from_outdir(bt_outdir) if bt_outdir else []
if samples:
    prev_sel = st.session_state.get("bt_selected_samples", [])
    if not isinstance(prev_sel, list):
        prev_sel = []

    if folder_changed:
        # Directory changed → auto-select all samples
        default_sel = samples.copy()
    else:
        # Same directory → keep only samples that still exist
        default_sel = [s for s in prev_sel if s in samples]
        if not default_sel:
            default_sel = samples.copy()

    st.session_state["bt_selected_samples"] = default_sel

    sel = st.multiselect(
        "Samples",
        options=samples,
        default=default_sel,
        key="bt_selected_samples",
    )
else:
    sel = []
    if bt_outdir:
        st.warning("No samples found in this directory.")

st.divider()
st.subheader("Species-specific tools")
help_popover("ℹ️ What are these?", HELP["species"])

# ------------------------- Species tools grid -------------------------
for genus, tools in SPECIES_TOOLS:
    with st.expander(genus, expanded=False):
        cols = st.columns(3)
        for i, (label, wf_name) in enumerate(tools):
            col = cols[i % 3]
            key = f"btsp_run_{wf_name}"
            col.checkbox(label, value=st.session_state.get(key, False), key=key)

# ------------------------- General parameters -------------------------
with st.expander("General parameters", expanded=True):
    btsp_profile = st.selectbox(
        "Profile (-profile)",
        ["docker", "singularity", "standard"],
        index=0,
        key="btsp_profile",
    )
    btsp_threads = st.slider(
        "--max_cpus",
        0,
        min(os.cpu_count() or 64, 128),
        0,
        1,
        key="btsp_threads",
    )
    btsp_memory_gb = st.slider(
        "--max_memory (GB)",
        0,
        256,
        0,
        1,
        key="btsp_memory_gb",
    )
    btsp_resume = st.checkbox("-resume", value=True, key="btsp_resume")
    btsp_extra = st.text_input(
        "Extras (raw line, optional)",
        key="btsp_extra",
        value=st.session_state.get("btsp_extra", ""),
        help="Additional flags for Nextflow/Bactopia (e.g.: -with-report, global parameters, etc.).",
    )
    help_popover("❓ Help (general parameters)", HELP["general"])

# ------------------------- Action bar (async execution) -------------------------
st.divider()
col1, col2 = st.columns([1, 1])
with col1:
    start_species = st.button(
        "▶️ Run species-specific tools (async)",
        key="btn_species_start",
        disabled=st.session_state.get("species_running", False),
    )
with col2:
    stop_species = st.button(
        "⏹️ Stop",
        key="btn_species_stop",
        disabled=not st.session_state.get("species_running", False),
    )

status_box_species = st.empty()
log_zone_species = st.empty()

if stop_species:
    utils.request_stop_ns("species")
    status_box_species.warning("Stop requested…")

if start_species:
    if not utils.nextflow_available():
        st.error("Nextflow not found (neither in PATH nor via BACTOPIA_ENV_PREFIX / NEXTFLOW_BIN / nextflow_bin).")
    else:
        if not bt_outdir:
            st.error("Please define the 'Bactopia results directory'.")
        else:
            # If nothing selected but we have samples, assume all
            if not sel and samples:
                sel = samples
                st.session_state["bt_selected_samples"] = sel
            if not sel:
                st.error("Select at least one sample.")
            else:
                include_file = write_include_file(bt_outdir, sel)
                tools_to_run: list[tuple[str, str]] = []

                for genus, tools in SPECIES_TOOLS:
                    for label, wf_name in tools:
                        key = f"btsp_run_{wf_name}"
                        if st.session_state.get(key):
                            tools_to_run.append((label, wf_name))

                if not tools_to_run:
                    st.warning("Select at least one species-specific tool.")
                else:
                    sub_cmds: list[str] = []
                    stdbuf = shutil.which("stdbuf")
                    for label, wf_name in tools_to_run:
                        extra: list[str] = []
                        # If in the future any species tool gets its own options, append them to 'extra'
                        cmdi = bt_nextflow_cmd(
                            wf_name,
                            bt_outdir,
                            include_file,
                            st.session_state.get("btsp_profile", "docker"),
                            st.session_state.get("btsp_threads") or None,
                            st.session_state.get("btsp_memory_gb") or None,
                            resume=st.session_state.get("btsp_resume", True),
                            extra=extra,
                        )
                        if stdbuf:
                            cmdi = f"{stdbuf} -oL -eL {cmdi}"
                        sub_cmds.append(
                            f'echo "===== [Bactopia Species] {label} ({wf_name}) =====" ; {cmdi}'
                        )

                    full_cmd = " ; ".join(sub_cmds)
                    status_box_species.info("Running species-specific tools (async).")
                    utils.start_async_runner_ns(full_cmd, "species")

# Live log update
if st.session_state.get("species_running", False):
    utils.drain_log_queue_ns("species", tail_limit=500, max_pull=800)
    utils.render_log_box_ns("species", height=520)
    finished = utils.check_status_and_finalize_ns("species", status_box_species)
    if not finished:
        time.sleep(0.3)
        utils._st_rerun()
else:
    utils.render_log_box_ns("species", height=520)

# ------------------------- merged-results -------------------------
st.divider()
st.subheader("merged-results (recent runs)")

runs_root = pathlib.Path(bt_outdir) / "bactopia-runs" if bt_outdir else None
if runs_root and runs_root.exists():
    runs = sorted(runs_root.glob("*"))
    if runs:
        latest = runs[-1]
        mr = latest / "merged-results"
        if mr.exists():
            for f in sorted(mr.glob("*.tsv")):
                st.markdown(f"- `{f.name}` — {f}")
        else:
            st.caption("No merged-results found for this run.")
    else:
        st.caption("There are no runs yet under bactopia-runs.")
else:
    st.caption("Directory bactopia-runs not found.")

DISCLAIMER_MD = """
> ⚠️ **Notice about Bactopia**
>
> This panel only orchestrates official **Bactopia** pipeline.  
> Bactopia is software developed by third parties (https://bactopia.github.io/latest/).  
> **BEAR-HUB** does not modify Bactopia's code; it only assembles commands
> and parameters in a more user-friendly way.
>
> For methods, limitations, and the correct way to cite Bactopia, always refer
> to the official documentation and repository.
"""

st.markdown(DISCLAIMER_MD)
