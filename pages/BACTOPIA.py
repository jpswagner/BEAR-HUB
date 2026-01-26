# BACTOPIA.py — Bactopia UI Local (FOFN-first, multi-sample)
# ---------------------------------------------------------------------
# • Streamlit interface to orchestrate Bactopia (via Nextflow) using FOFN only
# • FOFN generator with automatic runtype detection:
#     - paired-end (R1/R2)
#     - single-end (SE)
#     - ont (long reads)
#     - hybrid (PE + ONT in the same sample)
#     - assembly (FASTA)
# • No "single-sample" mode (all runs via --samples)
# • Only keeps --max_cpus and --max_memory (no -name or -work-dir)
# • Async execution with tailing logs and run cleaning
# • Optional Nextflow reports (-with-report / -with-timeline / -with-trace)
# • Safer NXF_HOME and .nextflow directory handling (avoid history.lock errors)
# • Integration with BACTOPIA_ENV_PREFIX (Nextflow from 'bactopia' env)
# • Automatic integration with ~/.bear-hub.env (if not already sourced)
# • Always uses '-profile docker' (Docker is required)
# ---------------------------------------------------------------------

"""
Bactopia Main Interface.

This module implements the primary interface for running the Bactopia pipeline.
It handles:
1.  **FOFN Generation**: Automatically scanning directories for FASTQ/FASTA files
    and creating a 'File Of File Names' (samples.txt) describing the samples.
2.  **Configuration**: Setting up Bactopia parameters (profile, resources, fastp, unicycler).
3.  **Execution**: Asynchronously running Nextflow/Bactopia commands.
4.  **Monitoring**: Real-time log tailing of the Nextflow execution.
5.  **Environment Management**: ensuring Nextflow and Docker availability.
"""

import os
import shlex
import time
import yaml
import pathlib
import re
import fnmatch
from typing import List, Dict, Tuple

import streamlit as st

# Import utility module from parent directory (or same directory if running from root)
try:
    import utils
except ImportError:
    import sys
    sys.path.append(str(pathlib.Path(__file__).parent.parent))
    import utils

# ============================= General config =============================
st.set_page_config(page_title="BEAR-HUB — Bactopia", page_icon="🐻", layout="wide")

APP_ROOT = pathlib.Path(__file__).resolve().parent

# Discover project root safely (folder that holds /static)
if (APP_ROOT / "static").is_dir():
    PROJECT_ROOT = APP_ROOT
elif (APP_ROOT.parent / "static").is_dir():
    PROJECT_ROOT = APP_ROOT.parent
else:
    PROJECT_ROOT = APP_ROOT  # fallback


APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
PRESETS_FILE = APP_STATE_DIR / "presets.yaml"
DEFAULT_PRESET_NAME = "default"

# Attempt to load .bear-hub.env early
utils.bootstrap_bear_env_from_file()

# Base working dir:
# - if BEAR_HUB_BASEDIR is defined: use it
# - otherwise: CWD (where ./run_bear.sh was called)
BASE_DIR = pathlib.Path(os.getenv("BEAR_HUB_BASEDIR", os.getcwd())).expanduser().resolve()

# Default outdir:
# - if BEAR_HUB_OUTDIR is defined: use it
# - otherwise: BASE_DIR / "bactopia_out"
env_out = os.getenv("BEAR_HUB_OUTDIR")
if env_out:
    DEFAULT_OUTDIR = str(pathlib.Path(env_out).expanduser().resolve())
else:
    DEFAULT_OUTDIR = str((BASE_DIR / "bactopia_out").resolve())

# Guarantee NXF_HOME on module load
utils.ensure_nxf_home()


# ============================= Presets =============================

PRESET_KEYS_ALLOWLIST = {
    # Execution
    "profile", "outdir", "datasets", "resume", "threads", "memory_gb",
    # FOFN generator
    "fofn_base", "fofn_recursive", "fofn_species", "fofn_gsize", "fofn_use",
    "fofn_long_reads", "fofn_infer_ont_by_name", "fofn_merge_multi", "fofn_include_assemblies",
    # Tools
    "fastp_mode", "fastp_dash3", "fastp_M", "fastp_W", "fastp_opts_text",
    "fastp_enable_5prime", "fastp_q_enable", "fastp_q", "fastp_l_enable", "fastp_l",
    "fastp_n", "fastp_u", "fastp_cut_right",
    "fastp_dedup", "fastp_correction", "fastp_poly_x", "fastp_overrep", "fastp_umi",
    "fastp_umi_loc", "fastp_umi_len",
    "fastp_detect_adapter_pe", "fastp_adapter_r1", "fastp_adapter_r2", "fastp_poly_g", "fastp_extra",
    # Assembler & Polishing
    "use_unicycler", "hybrid_strategy",
    "shovill_assembler", "shovill_opts", "shovill_kmers", "trim", "no_stitch", "no_corr",
    "dragonflye_assembler", "dragonflye_opts", "nanohq",
    "min_contig_len", "min_contig_cov", "reassemble", "no_rotate", "no_miniasm",
    "no_polish", "polypolish_rounds", "pilon_rounds", "racon_rounds", "medaka_rounds", "medaka_model",
    "unicycler_mode", "unicycler_min_len", "unicycler_extra",
    # Extra params and reports
    "extra_params", "with_report", "with_timeline", "with_trace",
}


def load_presets():
    """
    Load presets from the YAML state file.

    Returns:
        dict: A dictionary of loaded presets.
    """
    utils.ensure_state_dir()
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_presets(presets: dict):
    """
    Save presets to the YAML state file.

    Args:
        presets (dict): The dictionary of presets to save.
    """
    utils.ensure_state_dir()
    with open(PRESETS_FILE, "w", encoding="utf-8") as fh:
        yaml.safe_dump(presets, fh, sort_keys=True, allow_unicode=True)


def _snapshot_current_state() -> dict:
    """
    Capture the current session state values for allowlisted keys.

    Returns:
        dict: A subset of st.session_state containing only preset-relevant keys.
    """
    snap = {}
    for k in PRESET_KEYS_ALLOWLIST:
        if k in st.session_state:
            snap[k] = st.session_state[k]
    return snap


def _apply_dict_to_state(values: dict):
    """
    Update st.session_state with values from a dictionary.

    Args:
        values (dict): Key-value pairs to update in the session state.
    """
    for k, v in (values or {}).items():
        if k in PRESET_KEYS_ALLOWLIST:
            st.session_state[k] = v


def apply_preset_before_widgets():
    """
    Apply any pending preset values to the session state before widgets render.

    This ensures that when widgets are initialized, they pick up the values
    from the loaded preset.
    """
    pending = st.session_state.pop("__pending_preset_values", None)
    if pending:
        _apply_dict_to_state(pending)
        st.session_state["__preset_msg"] = st.session_state.get("__preset_msg") or "Preset applied."


def _cb_stage_apply_preset():
    """Callback to stage a preset for application on the next rerun."""
    name = st.session_state.get("__preset_to_load")
    if not name or name == "(none)":
        return
    presets = load_presets()
    st.session_state["__pending_preset_values"] = presets.get(name, {})
    st.session_state["__preset_msg"] = f"Preset staged: {name} (applied on this reload)"


def _cb_save_preset():
    """Callback to save the current state as a new preset."""
    name = (st.session_state.get("__preset_save_name") or "").strip() or DEFAULT_PRESET_NAME
    name = re.sub(r"\s+", "_", name)
    presets = load_presets()
    presets[name] = _snapshot_current_state()
    save_presets(presets)
    st.session_state["__preset_msg"] = f"Preset saved: {name}"


def _cb_delete_preset():
    """Callback to delete the selected preset."""
    name = st.session_state.get("__preset_to_load")
    if not name or name == "(none)":
        return
    presets = load_presets()
    if name in presets:
        del presets[name]
        save_presets(presets)
        st.session_state["__preset_msg"] = f"Preset deleted: {name}"


def render_presets_sidebar():
    """Render the Presets management interface in the sidebar."""
    st.header("Presets")
    presets = load_presets()
    names = sorted(presets.keys())
    st.selectbox("Load preset", ["(none)"] + names, key="__preset_to_load")
    st.text_input(
        "Save as (preset name)",
        key="__preset_save_name",
        placeholder="e.g., my_preset",
    )
    st.markdown('<div id="presets-section">', unsafe_allow_html=True)
    st.button("Apply", key="__btn_apply", on_click=_cb_stage_apply_preset)
    st.button("Save current", key="__btn_save", on_click=_cb_save_preset)
    st.button("Delete", key="__btn_delete", on_click=_cb_delete_preset)
    st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.get("__preset_msg"):
        st.caption(st.session_state["__preset_msg"])


apply_preset_before_widgets()

# ============================= Discovery / FOFN =============================

FASTQ_PATTERNS = ["*.fastq.gz", "*.fq.gz", "*.fastq", "*.fq"]
FA_PATTERNS = ["*.fna.gz", "*.fa.gz", "*.fasta.gz", "*.fna", "*.fa", "*.fasta"]


PE1_PATTERNS = [
    re.compile(r"^(?P<root>.+?)[._-](?:R?1|1|[Aa])(?:_[0-9]{3})?$", re.IGNORECASE),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_[Rr]1_\d{3}$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_1_\d{3}$"),
]
PE2_PATTERNS = [
    re.compile(r"^(?P<root>.+?)[._-](?:R?2|2|[Bb])(?:_[0-9]{3})?$", re.IGNORECASE),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_[Rr]2_\d{3}$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_2_\d{3}$"),
]
LANE_SUFFIX = re.compile(r"(_L\d{3,4})?(_\d{3})?$", re.IGNORECASE)


def _drop_exts(name: str) -> str:
    """Strip known FASTA/FASTQ extensions from a filename."""
    for ext in [".fastq.gz", ".fq.gz", ".fastq", ".fq", ".fna.gz", ".fa.gz", ".fasta.gz", ".fna", ".fa", ".fasta"]:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _infer_root_and_tag(path: pathlib.Path) -> Tuple[str, str]:
    """
    Infer the sample root name and type (PE1, PE2, SE) from a filename.

    Args:
        path (pathlib.Path): The path to the file.

    Returns:
        Tuple[str, str]: A tuple of (sample_root_name, tag). Tag is one of "PE1", "PE2", "SE".
    """
    name = _drop_exts(path.name)
    name = LANE_SUFFIX.sub("", name)
    for pat in PE1_PATTERNS:
        m = pat.match(name)
        if m:
            return m.group("root"), "PE1"
    for pat in PE2_PATTERNS:
        m = pat.match(name)
        if m:
            return m.group("root"), "PE2"
    return name, "SE"


def _is_probably_ont(p: pathlib.Path) -> bool:
    """Guess if a file is Nanopore based on common keywords in the path/name."""
    s = str(p.as_posix()).lower()
    return any(x in s for x in ["ont", "nanopore", "minion", "promethion", "fastq_pass", "guppy"])


def _collect_files(base: pathlib.Path, patterns: List[str], recursive: bool) -> List[pathlib.Path]:
    """
    Collect files matching patterns in a base directory.

    Args:
        base (pathlib.Path): Base directory.
        patterns (List[str]): List of glob patterns.
        recursive (bool): Whether to search recursively.

    Returns:
        List[pathlib.Path]: Sorted list of unique file paths.
    """
    out: List[pathlib.Path] = []
    for pat in patterns:
        out += list(base.rglob(pat) if recursive else base.glob(pat))
    clean = []
    for p in out:
        try:
            if p.is_file():
                clean.append(p.resolve())
        except Exception:
            pass
    return sorted(set(clean))


def discover_runs_and_build_fofn(base_dir: str,
                                 recursive: bool,
                                 species: str,
                                 gsize: str,
                                 fofn_path: str,
                                 treat_se_as_ont: bool,
                                 infer_ont_by_name: bool,
                                 merge_multi: bool,
                                 include_assemblies: bool) -> dict:
    """
    Scan a directory for sequencing files and build a FOFN (File Of File Names).

    Args:
        base_dir (str): Directory to scan.
        recursive (bool): Scan subdirectories.
        species (str): Species name to use in FOFN.
        gsize (str): Genome size string.
        fofn_path (str): Output path for the FOFN file.
        treat_se_as_ont (bool): Treat single-end reads as ONT.
        infer_ont_by_name (bool): Use filename heuristics to detect ONT.
        merge_multi (bool): Merge multiple files for same sample with commas.
        include_assemblies (bool): Include FASTA assemblies.

    Returns:
        dict: A dictionary containing:
            - rows: List of rows in the FOFN.
            - counts: Count of runtypes detected.
            - issues: List of potential issues/warnings.
            - header: The header columns of the FOFN.
            - fofn_path: Path to the generated file.
    """
    base = pathlib.Path(base_dir or ".")
    if not base.exists():
        raise FileNotFoundError("Base folder does not exist.")

    fofn_parent = pathlib.Path(fofn_path).parent
    fofn_parent.mkdir(parents=True, exist_ok=True)

    fq_files = _collect_files(base, FASTQ_PATTERNS, recursive)
    fa_files = _collect_files(base, FA_PATTERNS, recursive) if include_assemblies else []

    groups: Dict[str, Dict[str, List[str]]] = {}
    issues: List[str] = []

    for fq in fq_files:
        root, tag = _infer_root_and_tag(fq)
        d = groups.setdefault(root, {"pe1": [], "pe2": [], "se": [], "ont": [], "assembly": []})
        if tag == "PE1":
            d["pe1"].append(str(fq))
        elif tag == "PE2":
            d["pe2"].append(str(fq))
        else:
            if treat_se_as_ont or (infer_ont_by_name and _is_probably_ont(fq)):
                d["ont"].append(str(fq))
            else:
                d["se"].append(str(fq))

    for fa in fa_files:
        root = _drop_exts(fa.name)
        d = groups.setdefault(root, {"pe1": [], "pe2": [], "se": [], "ont": [], "assembly": []})
        d["assembly"].append(str(fa))

    header = ["sample", "runtype", "genome_size", "species", "r1", "r2", "extra"]
    rows: List[List[str]] = []

    def _join_or_pick(paths: List[str]) -> str:
        if not paths:
            return ""
        if merge_multi:
            return ",".join(paths)
        try:
            return sorted(
                paths,
                key=lambda p: pathlib.Path(p).stat().st_size if pathlib.Path(p).exists() else 0,
                reverse=True,
            )[0]
        except Exception:
            return paths[0]

    counts = {"paired-end": 0, "single-end": 0, "ont": 0, "hybrid": 0, "assembly": 0}

    for sample, parts in sorted(groups.items()):
        pe1 = parts["pe1"]
        pe2 = parts["pe2"]
        se = parts["se"]
        ont = parts["ont"]
        fa = parts["assembly"]

        if pe1 and not pe2:
            issues.append(f"{sample}: R1 found without R2.")
        if pe2 and not pe1:
            issues.append(f"{sample}: R2 found without R1.")

        if fa and not (pe1 or pe2 or se or ont):
            runtype = "assembly"
            r1 = ""
            r2 = ""
            extra = _join_or_pick(fa)
        elif pe1 and pe2 and ont:
            runtype = "hybrid"
            r1 = _join_or_pick(pe1)
            r2 = _join_or_pick(pe2)
            extra = _join_or_pick(ont)
        elif pe1 and pe2:
            runtype = "paired-end"
            r1 = _join_or_pick(pe1)
            r2 = _join_or_pick(pe2)
            extra = ""
        elif ont and not (pe1 or pe2):
            runtype = "ont"
            r1 = _join_or_pick(ont)
            r2 = ""
            extra = ""
        elif se and not (pe1 or pe2 or ont):
            runtype = "single-end"
            r1 = _join_or_pick(se)
            r2 = ""
            extra = ""
        elif fa and (pe1 or pe2 or se or ont):
            issues.append(
                f"{sample}: FASTA and FASTQ detected; ignoring assembly in FOFN "
                "(use only one type per sample)."
            )
            if pe1 and pe2 and ont:
                runtype = "hybrid"
                r1 = _join_or_pick(pe1)
                r2 = _join_or_pick(pe2)
                extra = _join_or_pick(ont)
            elif pe1 and pe2:
                runtype = "paired-end"
                r1 = _join_or_pick(pe1)
                r2 = _join_or_pick(pe2)
                extra = ""
            elif ont:
                runtype = "ont"
                r1 = _join_or_pick(ont)
                r2 = ""
                extra = ""
            else:
                runtype = "single-end"
                r1 = _join_or_pick(se)
                r2 = ""
        else:
            issues.append(f"{sample}: could not classify sample (missing files?).")
            continue

        counts[runtype] = counts.get(runtype, 0) + 1
        rows.append([sample, runtype, gsize, species, r1, r2, extra])

        for label, arr in [("PE1", pe1), ("PE2", pe2), ("ONT", ont), ("SE", se)]:
            if len(arr) > 1 and not merge_multi:
                issues.append(
                    f"{sample}: multiple files under {label}; using the largest file. "
                    "Enable 'Merge' to concatenate them with commas."
                )

    with open(fofn_path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(map(str, r)) + "\n")

    return {
        "rows": rows,
        "counts": counts,
        "issues": issues,
        "header": header,
        "fofn_path": fofn_path,
    }

# ============================= Sidebar =============================

ICON_PATH = PROJECT_ROOT / "static" / "bear-hub-icon.png"

with st.sidebar:
    st.markdown("---")
    st.header("Environment")
    nf_ok = utils.nextflow_available()
    docker_ok = utils.docker_available()
    st.write(
        f"Nextflow: {'✅' if nf_ok else '❌'} | "
        f"Docker: {'✅' if docker_ok else '❌'}"
    )
    st.caption(
        "This app runs Bactopia **exclusively** with `-profile docker`.\n"
        "Docker must be installed and accessible to the user running Streamlit."
    )
    if not nf_ok:
        st.error("Nextflow not found (neither in PATH nor in BACTOPIA_ENV_PREFIX).", icon="⚠️")
    else:
        # We can't easily access BACTOPIA_NEXTFLOW_BIN from here since it's local in utils
        # But we can call utils.get_nextflow_bin()
        nf_bin = utils.get_nextflow_bin()
        if nf_bin != "nextflow":
            st.caption(f"Nextflow via Bactopia env: `{nf_bin}`")
        else:
            st.caption("Nextflow found via system PATH.")

    if not docker_ok:
        st.error(
            "Docker is not available. Install and enable Docker before running Bactopia.",
            icon="⚠️",
        )

    # We can check BACTOPIA_ENV_PREFIX from os.environ since utils sets it
    bactopia_env_prefix = os.environ.get("BACTOPIA_ENV_PREFIX")
    if bactopia_env_prefix:
        st.caption(f"BACTOPIA_ENV_PREFIX: `{bactopia_env_prefix}`")

    st.divider()
    render_presets_sidebar()

st.markdown(
    """
<style>
[data-testid="stSidebar"] #presets-section,
[data-testid="stSidebar"] #presets-section .stElementContainer,
[data-testid="stSidebar"] #presets-section .stButton { width: 100% !important; }
[data-testid="stSidebar"] #presets-section .stButton > button {
  width: 100% !important; min-height: 42px !important; display: flex !important;
  align-items: center !important; justify-content: center !important; border-radius: 8px !important;
}
[data-testid="stSidebar"] #presets-section .stButton > button div[data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] #presets-section .stButton > button div[data-testid="stMarkdownContainer"] p {
  margin: 0 !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
}
button[kind="secondary"] span, button[kind="secondary"] div { white-space: nowrap !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ============================= Page header =============================

ICON_PATH_BACTOPIA = PROJECT_ROOT / "static" / "bear-bactopia-icon.png"

if ICON_PATH_BACTOPIA.is_file():
    st.image(str(ICON_PATH_BACTOPIA), width=500)
else:
    st.title("🧬 Bactopia UI")

# ============================= Main parameters =============================

st.subheader("Main parameters")
with st.expander("Global parameters", expanded=False):
    colA, colB = st.columns(2)
    with colA:
        # Force '-profile docker' always
        st.session_state["profile"] = "docker"
        st.text_input(
            "Profile (-profile)",
            key="profile",
            disabled=True,
            help="This app always uses '-profile docker' for Bactopia.",
        )

        outdir = utils.path_picker(
            "Outdir (results root)",
            key="outdir",
            mode="dir",
            start=DEFAULT_OUTDIR,
            help="Folder where Nextflow/Bactopia will write output.",
        )
        datasets = utils.path_picker(
            "datasets/ (optional)",
            key="datasets",
            mode="dir",
            start=str(pathlib.Path.home()),
        )
    with colB:
        resume = st.checkbox("-resume (resume previous runs)", value=True, key="resume")
        max_cpus_default = min(os.cpu_count() or 64, 128)
        threads = st.slider("--max_cpus", 0, max_cpus_default, 0, 1, key="threads")
        memory_gb = st.slider("--max_memory (GB)", 0, 256, 0, 1, key="memory_gb")

# ============================= FOFN (multi-sample) =============================

FOFN_HELP_MD = r"""
# ℹ️ FOFN generator — how it works

The generator scans a **base folder** and produces a `samples.txt` (FOFN) in the format
expected by Bactopia, automatically detecting the **runtype** of each sample:
**paired-end**, **single-end**, **ont**, **hybrid** (PE + ONT), and **assembly**.

- It traverses the folder (and optionally subfolders) looking for:
  - FASTQ/FASTQ.GZ (`*.fastq.gz`, `*.fq.gz`, `*.fastq`, `*.fq`)
  - FASTA (`*.fa`, `*.fna`, `*.fasta`, and `.gz` variants) — if "Include assemblies" is enabled.
- It tries to group files by a root name (before R1/R2, lane, etc.).
- It identifies:
  - `R1` / `R2` using common naming patterns (R1/R2, _1/_2, A/B, etc.).
  - Long reads (ONT) either by:
    - name heuristics (ont|nanopore|minion|promethion|fastq_pass|guppy) **or**
    - "Treat SE as ONT" option.

The generated FOFN has columns:

`sample  runtype  genome_size  species  r1  r2  extra`

- `sample`: sample name (inferred root).
- `runtype`: one of `paired-end`, `single-end`, `ont`, `hybrid`, `assembly`.
- `genome_size` and `species`: copied from the corresponding fields in the UI.
- `r1`, `r2`, `extra`:
  - `paired-end`: `r1` = R1 fastq(s), `r2` = R2 fastq(s).
  - `single-end`: `r1` = SE fastq(s).
  - `ont`: `r1` = ONT fastq(s).
  - `hybrid`: `r1` = PE R1, `r2` = PE R2, `extra` = ONT fastq(s).
  - `assembly`: `extra` = FASTA path.

If **"Merge multiple files with commas"** is enabled, multiple files in the same
category (e.g. multiple R1) are concatenated into a single field separated by commas
(as Bactopia expects).

If it is disabled, the generator picks only the **largest** file per group and
adds a warning about this in the summary.
"""

st.subheader("Generate FOFN (multiple samples)", help=FOFN_HELP_MD)

with st.expander("Generate FOFN", expanded=False):
    # Default base: BEAR_HUB_DATA (if any) or BASE_DIR
    base_default = os.getenv("BEAR_HUB_DATA", str(BASE_DIR))
    base_dir = utils.path_picker(
        "Base folder with FASTQs/FASTAs",
        key="fofn_base",
        mode="dir",
        start=base_default,
        help=(
            "In local conda installs, use normal paths (e.g., /mnt/HD/...). "
            "If running inside Docker, your host filesystem may be mounted under /hostfs "
            "(e.g., /hostfs/mnt/HD/...)."
        ),
        patterns=FASTQ_PATTERNS + FA_PATTERNS,
    )

    recursive = st.checkbox("Include subfolders", value=True, key="fofn_recursive")

    cA, cB, cC = st.columns(3)
    with cA:
        species_in = st.text_input(
            "species (optional)",
            value=st.session_state.get("fofn_species", "UNKNOWN_SPECIES"),
            key="fofn_species",
        )
    with cB:
        # Predefined sizes from utils.GENOME_SIZES plus a Custom option
        _gsize_opts = ["(Select or Custom)"] + utils.GENOME_SIZES + ["Custom"]
        _gsize_sel = st.selectbox(
            "genome_size (optional)",
            options=_gsize_opts,
            index=0,
            key="_fofn_gsize_select",
            help="Select a common genome size or enter a custom value (e.g., '2.8m' or bytes).",
        )
        if _gsize_sel == "Custom":
            gsize_in = st.text_input(
                "Custom genome size",
                value=st.session_state.get("fofn_gsize", "0"),
                key="fofn_gsize",
            )
        elif _gsize_sel and _gsize_sel != "(Select or Custom)":
            # Convert "2.0 Mb" -> "2000000" approx, or just pass the string if Bactopia accepts it.
            # Bactopia usually expects an integer (bytes) or string with unit.
            # We will strip " Mb" and multiply by 1,000,000 for safety, as '2.0 Mb' string might not be parsed correctly by all tools.
            try:
                val_float = float(_gsize_sel.replace(" Mb", ""))
                gsize_in = str(int(val_float * 1000000))
            except Exception:
                gsize_in = _gsize_sel
            # Update the underlying key used by the scanner
            st.session_state["fofn_gsize"] = gsize_in
        else:
            # Fallback or empty
            gsize_in = st.session_state.get("fofn_gsize", "0")

    with cC:
        st.checkbox("Include assemblies (FASTA)", value=True, key="fofn_include_assemblies")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox(
            "Treat SE as ONT (long reads)",
            value=False,
            key="fofn_long_reads",
            help="Equivalent to --long_reads from 'bactopia prepare'.",
        )
    with c2:
        st.checkbox(
            "Heuristic: infer ONT by name (ont|nanopore|...)",
            value=True,
            key="fofn_infer_ont_by_name",
        )
    with c3:
        st.checkbox(
            "Merge multiple files with commas",
            value=True,
            key="fofn_merge_multi",
            help="If disabled, only the largest file per category (PE1/PE2/ONT/SE) is used.",
        )

    fofn_out = str((pathlib.Path(st.session_state.get("outdir", DEFAULT_OUTDIR)) / "samples.txt").resolve())
    st.caption(f"FOFN will be saved/updated at: `{fofn_out}`")

    if st.button("🔎 Scan base folder and build FOFN", key="btn_scan_fofn"):
        try:
            res = discover_runs_and_build_fofn(
                base_dir=base_dir,
                recursive=recursive,
                species=species_in,
                gsize=gsize_in,
                fofn_path=fofn_out,
                treat_se_as_ont=st.session_state.get("fofn_long_reads", False),
                infer_ont_by_name=st.session_state.get("fofn_infer_ont_by_name", True),
                merge_multi=st.session_state.get("fofn_merge_multi", True),
                include_assemblies=st.session_state.get("fofn_include_assemblies", True),
            )
            st.success(f"FOFN saved/updated: {res['fofn_path']}")
            try:
                import pandas as pd
                df = pd.DataFrame(res["rows"], columns=res["header"])
                st.dataframe(df.head(1000), use_container_width=True)
            except Exception:
                st.write("Total rows:", len(res["rows"]))
            st.info(
                "Runtype summary: "
                + ", ".join([f"{k}={v}" for k, v in res["counts"].items()])
            )
            if res["issues"]:
                st.warning("Potential issues detected:")
                for msg in res["issues"]:
                    st.markdown(f"- {msg}")
        except Exception as e:
            st.error(f"Failed to generate FOFN: {e}")

st.session_state["fofn_use"] = True

# ============================= FASTP / Unicycler =============================

FASTP_HELP_MD = """
# ℹ️ fastp — explanation of parameters shown in the UI

This panel builds the `--fastp_opts` string used by Bactopia. Main options:

- **Sliding Window Cutting**:
  - `-3` (`--cut_tail`): Move sliding window from tail (3') to front.
  - `-5` (`--cut_front`): Move sliding window from front (5') to tail.
  - `-r` (`--cut_right`): Sliding window from front to tail, drop remaining if quality fail.
  - `-M` (`--cut_mean_quality`): Min mean quality in the sliding window.
  - `-W` (`--cut_window_size`): Size of the sliding window.
- **Filters**:
  - `-q`: Min quality value for a qualified base.
  - `-l`: Min read length allowed.
  - `-n`: Max N bases allowed.
  - `-u`: Max % of unqualified bases allowed.
  - `-p` (`--overrepresentation_analysis`): Enable overrepresented sequence analysis.
- **Processing**:
  - `-D` (`--dedup`): Enable deduplication.
  - `-c` (`--correction`): Enable base correction in overlapped regions (PE only).
  - `-g`: Trim polyG in 3' ends (NextSeq/NovaSeq).
  - `-x` (`--trim_poly_x`): Trim polyX in 3' ends.
  - `-U` (`--umi`): Enable UMI processing (requires location/length).
  - `--detect_adapter_for_pe`: Detect adapters in PE data.
  - `-a`: Adapter sequence for Read 1.
  - `--adapter_sequence_r2`: Adapter sequence for Read 2.

The "Advanced extra (append)" text field lets you add any extra fastp flags.
"""

st.subheader("Read Cleaning (Fastp)", help=FASTP_HELP_MD)

with st.expander("fastp options", expanded=False):
    fastp_mode = st.radio(
        "Mode",
        ["Simple (recommended)", "Advanced (full line)"],
        index=0,
        key="fastp_mode",
        horizontal=True,
    )
    if fastp_mode.startswith("Simple"):
        st.markdown("**Sliding Window / Cutting**")
        topA, topB, topC = st.columns([2, 1, 1])
        with topA:
            st.checkbox("Cut Tail (3') sliding window (-3)", value=True, key="fastp_dash3")
            st.checkbox("Cut Front (5') sliding window (-5)", value=False, key="fastp_enable_5prime")
            st.checkbox("Cut Right sliding window (-r)", value=False, key="fastp_cut_right")
        with topB:
            st.slider("Mean Quality Threshold (-M)", 0, 40, 20, 1, key="fastp_M")
        with topC:
            st.slider("Window Size (-W)", 1, 50, 5, 1, key="fastp_W")

        st.markdown("**Quality & Length Filters**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("Quality Filter (-q)", value=False, key="fastp_q_enable")
            if st.session_state.get("fastp_q_enable"):
                st.slider("Value for -q", 0, 40, 20, 1, key="fastp_q")
        with c2:
            st.checkbox("Min Length Filter (-l)", value=False, key="fastp_l_enable")
            if st.session_state.get("fastp_l_enable"):
                st.slider("Value for -l", 0, 500, 15, 1, key="fastp_l")
        with c3:
            st.number_input("Max N Bases (-n)", min_value=0, max_value=10, value=0, step=1, key="fastp_n")
            st.number_input("Max % Unqualified Bases (-u)", min_value=0, max_value=100, value=0, step=1, key="fastp_u")

        st.markdown("**Adapters**")
        ad1, ad2, ad3 = st.columns(3)
        with ad1:
             st.checkbox("Detect Adapters (PE)", value=False, key="fastp_detect_adapter_pe")
        with ad2:
             st.text_input("Adapter Sequence (R1)", key="fastp_adapter_r1", placeholder="AGATCGGAAG...")
        with ad3:
             st.text_input("Adapter Sequence (R2)", key="fastp_adapter_r2", placeholder="AGATCGGAAG...")

        st.markdown("**Additional Processing**")
        ap1, ap2, ap3, ap4 = st.columns(4)
        with ap1:
            st.checkbox("Deduplication (-D)", value=False, key="fastp_dedup")
            st.checkbox("Base Correction (-c)", value=False, key="fastp_correction", help="PE only")
        with ap2:
            st.checkbox("Trim polyG (-g)", value=False, key="fastp_poly_g")
            st.checkbox("Trim polyX (-x)", value=False, key="fastp_poly_x")
        with ap3:
            st.checkbox("Overrepresentation (-p)", value=False, key="fastp_overrep")
        with ap4:
            st.checkbox("UMI Processing (-U)", value=False, key="fastp_umi")
            if st.session_state.get("fastp_umi"):
                st.selectbox("UMI Location", ["index1", "index2", "read1", "read2", "per_index", "per_read"], key="fastp_umi_loc")
                st.number_input("UMI Length", min_value=0, max_value=50, value=0, step=1, key="fastp_umi_len")

        fastp_extra = st.text_input(
            "Advanced extra (append)",
            value=st.session_state.get("fastp_extra", ""),
            key="fastp_extra",
        )

        parts = []
        # Sliding window logic: -3, -5, -r share -M and -W
        # fastp docs say -3/-5/-r use -M/-W if specific ones aren't set.
        # We only expose the global -M/-W to simplify.
        if st.session_state.get("fastp_dash3", True):
            parts.append("-3")
        if st.session_state.get("fastp_enable_5prime"):
            parts.append("-5")
        if st.session_state.get("fastp_cut_right"):
            parts.append("-r")
        
        parts += ["-M", str(st.session_state.get("fastp_M", 20))]
        parts += ["-W", str(st.session_state.get("fastp_W", 5))]

        if st.session_state.get("fastp_q_enable"):
            parts += ["-q", str(st.session_state.get("fastp_q", 20))]
        if st.session_state.get("fastp_l_enable"):
            parts += ["-l", str(st.session_state.get("fastp_l", 15))]
        
        n_val = st.session_state.get("fastp_n", 0)
        u_val = st.session_state.get("fastp_u", 0)
        if n_val:
            parts += ["-n", str(n_val)]
        if u_val:
            parts += ["-u", str(u_val)]

        if st.session_state.get("fastp_dedup"):
            parts.append("-D")
        if st.session_state.get("fastp_correction"):
            parts.append("-c")
        if st.session_state.get("fastp_poly_g"):
            parts.append("-g")
        if st.session_state.get("fastp_poly_x"):
            parts.append("-x")
        if st.session_state.get("fastp_detect_adapter_pe"):
            parts.append("--detect_adapter_for_pe")
        
        if (st.session_state.get("fastp_adapter_r1") or "").strip():
             parts.append(f"-a {shlex.quote(st.session_state['fastp_adapter_r1'].strip())}")
        if (st.session_state.get("fastp_adapter_r2") or "").strip():
             parts.append(f"--adapter_sequence_r2 {shlex.quote(st.session_state['fastp_adapter_r2'].strip())}")

        if st.session_state.get("fastp_overrep"):
            parts.append("-p")
        
        if st.session_state.get("fastp_umi"):
            parts.append("-U")
            loc = st.session_state.get("fastp_umi_loc")
            length = st.session_state.get("fastp_umi_len", 0)
            if loc:
                parts.append(f"--umi_loc={loc}")
            if length > 0:
                parts.append(f"--umi_len={length}")

        if (st.session_state.get("fastp_extra") or "").strip():
            parts.append(st.session_state["fastp_extra"].strip())

        fastp_opts_value = " ".join(parts)
        st.caption(f"**fastp_opts:** `{fastp_opts_value}`")
    else:
        fastp_opts_value = st.text_input(
            "Full fastp line (advanced)",
            value=st.session_state.get("fastp_opts_text", "-3 -M 20 -W 5"),
            key="fastp_opts_text",
        )

# ============================= Assembler & Polishing =============================

ASSEMBLER_HELP = """
# ℹ️ Assembler & Polishing Configuration

This section allows you to customize the assembly process for different read types and hybrid strategies.

### Strategies
- **Use Unicycler for PE**: Enables Unicycler for Illumina paired-end assembly instead of Shovill.
- **Hybrid Strategy**:
  - **Auto**: Bactopia defaults (usually Unicycler).
  - **Unicycler (--hybrid)**: Short-read assembly -> Long-read bridging -> Short-read polish.
  - **Dragonflye (--short_polish)**: Long-read assembly -> Short-read polish (Recommended for high coverage ONT).

### Assemblers
- **Shovill (Illumina)**: Default is `skesa`.
- **Dragonflye (ONT)**: Default is `flye`.

### Polishing
- **Rounds**: Number of iterations for each polishing tool.
- **No Polish**: Skips all polishing steps.
"""

st.subheader("Assembler & Polishing", help=ASSEMBLER_HELP)

with st.expander("Assembler & Polishing Settings", expanded=False):
    st.markdown("**Strategies**")
    strat_col1, strat_col2 = st.columns(2)
    with strat_col1:
        st.checkbox("--use_unicycler (for PE)", value=False, key="use_unicycler", help="Use Unicycler instead of Shovill for paired-end reads.")
    with strat_col2:
        st.radio("Hybrid Strategy", ["(Auto)", "Unicycler (--hybrid)", "Dragonflye (--short_polish)"], index=0, key="hybrid_strategy", horizontal=True)

    st.divider()

    st.markdown("**Assembler Selection**")
    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown("##### Shovill (Illumina)")
        st.selectbox("Assembler", ["skesa", "spades", "velvet", "megahit"], index=0, key="shovill_assembler")
        st.text_input("Extra Opts (--shovill_opts)", key="shovill_opts")
        st.text_input("K-mers (--shovill_kmers)", key="shovill_kmers", placeholder="e.g. 21,33,55")
        st.checkbox("--trim (Adaptor trimming)", value=False, key="trim")
        st.checkbox("--no_stitch (Disable PE stitching)", value=False, key="no_stitch")
        st.checkbox("--no_corr (Disable post-correction)", value=False, key="no_corr")

    with ac2:
        st.markdown("##### Dragonflye (ONT)")
        st.selectbox("Assembler", ["flye", "miniasm", "raven"], index=0, key="dragonflye_assembler")
        st.text_input("Extra Opts (--dragonflye_opts)", key="dragonflye_opts")
        st.checkbox("--nanohq (Flye NanoHQ mode)", value=False, key="nanohq")
        st.checkbox("--no_miniasm (Skip miniasm bridging)", value=False, key="no_miniasm")

    st.divider()

    st.markdown("**General Assembly Options**")
    # Ensuring 5 columns are allocated
    gc1, gc2, gc3, gc4, gc5 = st.columns(5)
    with gc1:
        st.number_input("Min Contig Len", min_value=0, value=500, key="min_contig_len", help="--min_contig_len")
    with gc2:
        st.number_input("Min Coverage", min_value=0, value=10, key="min_contig_cov", help="--min_contig_cov")
    with gc3:
        st.checkbox("--reassemble", value=False, key="reassemble", help="Re-assemble simulated reads")
    with gc4:
        st.checkbox("--no_rotate", value=False, key="no_rotate", help="Do not rotate to start gene")
    with gc5:
        st.checkbox("--skip_qc_plot", value=True, key="skip_qc_plot", help="Skip the QC plot generation")

    st.divider()

    st.markdown("**Polishing Options**")
    st.checkbox("--no_polish (Skip all polishing)", value=False, key="no_polish")
    
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        st.number_input("Polypolish Rounds", min_value=0, value=1, key="polypolish_rounds")
    with pc2:
        st.number_input("Pilon Rounds", min_value=0, value=0, key="pilon_rounds", help="Default is usually 0 unless specified")
    with pc3:
        st.number_input("Racon Rounds", min_value=0, value=1, key="racon_rounds")
    with pc4:
        st.number_input("Medaka Rounds", min_value=0, value=0, key="medaka_rounds", help="Default usually 0 (auto)")
    
    st.text_input("Medaka Model (--medaka_model)", key="medaka_model")

    st.divider()

    st.markdown("**Unicycler Advanced Options**")
    st.caption("These apply when Unicycler is used (either via --use_unicycler or --hybrid).")
    uc1, uc2 = st.columns(2)
    with uc1:
        st.radio("Mode", ["conservative", "normal", "bold"], index=1, key="unicycler_mode", horizontal=True)
    with uc2:
        st.number_input("min_fasta_length (Unicycler)", 0, 100000, 1000, 100, key="unicycler_min_len")
    st.text_input(
        "Unicycler Extra (append)",
        value=st.session_state.get("unicycler_extra", ""),
        key="unicycler_extra",
    )
    
    # Build Unicycler Opts String
    uni_parts = ["--mode", st.session_state.get("unicycler_mode", "normal")]
    if st.session_state.get("unicycler_min_len", 1000):
        uni_parts += ["--min_fasta_length", str(int(st.session_state["unicycler_min_len"]))]
    if (st.session_state.get("unicycler_extra") or "").strip():
        uni_parts.append(st.session_state["unicycler_extra"].strip())
    unicycler_opts_value = " ".join(uni_parts)
    st.caption(f"unicycler_opts: `{unicycler_opts_value}`")

# ============================= Annotation & Typing (AMRFinder+ / MLST) =============================

with st.expander("Annotation & Typing (AMRFinder+ / MLST)", expanded=False):
    st.markdown("#### AMRFinder+")
    amr1, amr2, amr3 = st.columns(3)
    with amr1:
        st.number_input("--ident_min (AMRFinder)", 0.0, 1.0, 0.9, 0.01, key="amr_ident_min")
    with amr2:
        st.number_input("--coverage_min (AMRFinder)", 0.0, 1.0, 0.6, 0.01, key="amr_coverage_min")

    st.divider()

    st.markdown("#### MLST")
    # Use utils.MLST_SCHEMES keys for the dropdown (Display Names)
    _mlst_opts = ["(auto/none)"] + sorted(utils.MLST_SCHEMES.keys())
    st.selectbox(
        "Scheme (--scheme)",
        options=_mlst_opts,
        index=0,
        key="mlst_scheme_display",
        help="Specify an MLST scheme. Leave as (auto/none) to skip or use default detection."
    )

# ============================= Extra params + reports =============================

extra_params_input = st.text_input(
    "Extra parameters (raw line)",
    value=st.session_state.get("extra_params", ""),
    key="extra_params",
)
computed_extra = extra_params_input
if st.session_state.get("fofn_use") and "fofn_out" in locals() and fofn_out:
    computed_extra = (computed_extra + f" --samples {shlex.quote(fofn_out)}").strip()

with st.expander("Reports (Nextflow)", expanded=False):
    rep = st.checkbox("-with-report", value=True, key="with_report")
    tim = st.checkbox("-with-timeline", value=True, key="with_timeline")
    trc = st.checkbox("-with-trace", value=True, key="with_trace")

# ============================= Command building =============================

def build_bactopia_cmd(params: dict) -> str:
    """
    Construct the full Bactopia/Nextflow command string.

    Args:
        params (dict): Dictionary of parameters (profile, outdir, etc.).

    Returns:
        str: The full shell command to execute.
    """
    # This app enforces '-profile docker' (container execution)
    profile = params.get("profile") or "docker"
    outdir = params.get("outdir", DEFAULT_OUTDIR)
    datasets = params.get("datasets")
    fastp_opts = params.get("fastp_opts")
    unicycler_opts = params.get("unicycler_opts")
    extra = params.get("extra_params")
    
    # Assembler & Polishing flags
    assembler_flags = params.get("assembler_flags", [])
    
    resume = params.get("resume", True)
    threads = params.get("threads")
    memory = params.get("memory")
    with_report = params.get("with_report")
    with_timeline = params.get("with_timeline")
    with_trace = params.get("with_trace")

    # Ensure outdir exists and has its own .nextflow/
    outdir_path = pathlib.Path(outdir).expanduser().resolve()
    outdir_path.mkdir(parents=True, exist_ok=True)
    utils.ensure_project_nxf_dir(outdir_path)
    utils.ensure_nxf_home()

    nf_bin = utils.get_nextflow_bin()

    base: List[str] = [
        nf_bin, "run", "bactopia/bactopia",
        "-profile", profile,
        "--outdir", str(outdir_path),
    ]
    if datasets:
        base += ["--datasets", datasets]

    report_dir = outdir_path
    if with_report:
        base += ["-with-report", str(report_dir / "nf-report.html")]
    if with_timeline:
        base += ["-with-timeline", str(report_dir / "nf-timeline.html")]
    if with_trace:
        base += ["-with-trace", str(report_dir / "nf-trace.txt")]

    if fastp_opts:
        base += ["--fastp_opts", fastp_opts]
    if unicycler_opts:
        base += ["--unicycler_opts", unicycler_opts]
    
    if assembler_flags:
        base += assembler_flags

    if threads:
        base += ["--max_cpus", str(threads)]
    if memory:
        base += ["--max_memory", memory]
    if resume:
        base += ["-resume"]

    if extra:
        base += shlex.split(extra)

    nf_cmd = " ".join(shlex.quote(x) for x in base)
    # Run Nextflow from outdir so that .nextflow/history lives there
    full_cmd = f"cd {shlex.quote(str(outdir_path))} && {nf_cmd}"
    return full_cmd


params = {
    "profile": st.session_state.get("profile"),
    "outdir": st.session_state.get("outdir"),
    "datasets": st.session_state.get("datasets") or None,
    "fastp_opts": (fastp_opts_value.strip() if "fastp_opts_value" in locals() and fastp_opts_value.strip() else None),
    "unicycler_opts": (unicycler_opts_value.strip() if "unicycler_opts_value" in locals() and unicycler_opts_value.strip() else None),
    "extra_params": computed_extra or None,
    "assembler_flags": [], # Populated below
    "resume": st.session_state.get("resume", True),
    "threads": st.session_state.get("threads") or None,
    "memory": (f"{st.session_state.get('memory_gb')} GB" if st.session_state.get("memory_gb") else None),
    "with_report": st.session_state.get("with_report", True),
    "with_timeline": st.session_state.get("with_timeline", True),
    "with_trace": st.session_state.get("with_trace", True),
}

# --- Populate Assembler Flags ---
af = []
if st.session_state.get("use_unicycler"):
    af.append("--use_unicycler")

hyb = st.session_state.get("hybrid_strategy")
if hyb == "Unicycler (--hybrid)":
    af.append("--hybrid")
elif hyb == "Dragonflye (--short_polish)":
    af.append("--short_polish")

if st.session_state.get("shovill_assembler") and st.session_state.get("shovill_assembler") != "skesa":
    af.extend(["--shovill_assembler", str(st.session_state["shovill_assembler"])])

if st.session_state.get("dragonflye_assembler") and st.session_state.get("dragonflye_assembler") != "flye":
    af.extend(["--dragonflye_assembler", str(st.session_state["dragonflye_assembler"])])

if st.session_state.get("shovill_opts"):
    # Pass the raw string; utils.run_cmd handles quoting of arguments.
    af.extend(["--shovill_opts", str(st.session_state["shovill_opts"])])
if st.session_state.get("shovill_kmers"):
    af.extend(["--shovill_kmers", str(st.session_state["shovill_kmers"])])
if st.session_state.get("dragonflye_opts"):
    af.extend(["--dragonflye_opts", str(st.session_state["dragonflye_opts"])])

if st.session_state.get("trim"): af.append("--trim")
if st.session_state.get("no_stitch"): af.append("--no_stitch")
if st.session_state.get("no_corr"): af.append("--no_corr")
if st.session_state.get("nanohq"): af.append("--nanohq")
if st.session_state.get("no_miniasm"): af.append("--no_miniasm")
if st.session_state.get("reassemble"): af.append("--reassemble")
if st.session_state.get("no_rotate"): af.append("--no_rotate")

if st.session_state.get("min_contig_len") != 500:
    af.extend(["--min_contig_len", str(st.session_state.get("min_contig_len"))])
if st.session_state.get("min_contig_cov") != 2:
    af.extend(["--min_contig_cov", str(st.session_state.get("min_contig_cov"))])

if st.session_state.get("skip_qc_plot"):
    af.append("--skip_qc_plot")

if st.session_state.get("no_polish"):
    af.append("--no_polish")

# AMRFinder+ params
# We compare against the tool's underlying defaults (not our UI defaults) to ensure flags are passed when needed.
# Default ident_min is -1 (per docs), so pass if different (e.g. our 0.9 default).
if st.session_state.get("amr_ident_min") != -1:
    af.extend(["--amrfinderplus_ident_min", str(st.session_state.get("amr_ident_min"))])
# Default coverage_min is 0.5 (per docs). Our UI default is 0.6.
# If it is not 0.5, we pass the flag. This ensures 0.6 is passed.
if st.session_state.get("amr_coverage_min") != 0.5:
    af.extend(["--amrfinderplus_coverage_min", str(st.session_state.get("amr_coverage_min"))])

# MLST params
_scheme_disp = st.session_state.get("mlst_scheme_display")
if _scheme_disp and _scheme_disp != "(auto/none)":
    # Retrieve the code from the map
    _code = utils.MLST_SCHEMES.get(_scheme_disp)
    if _code:
        # Pass the code directly. No quotes needed for single-word codes.
        af.extend(["--scheme", _code])

# Polishing rounds (only add if diff from defaults or explicit)
# Defaults: polypolish=1, racon=1. pilon/medaka usually conditional/0.
if st.session_state.get("polypolish_rounds", 1) != 1:
    af.extend(["--polypolish_rounds", str(st.session_state.get("polypolish_rounds"))])
if st.session_state.get("pilon_rounds", 0) > 0:
    af.extend(["--pilon_rounds", str(st.session_state.get("pilon_rounds"))])
if st.session_state.get("racon_rounds", 1) != 1:
    af.extend(["--racon_rounds", str(st.session_state.get("racon_rounds"))])
if st.session_state.get("medaka_rounds", 0) > 0:
    af.extend(["--medaka_rounds", str(st.session_state.get("medaka_rounds"))])
if st.session_state.get("medaka_model"):
    af.extend(["--medaka_model", str(st.session_state.get("medaka_model"))])

params["assembler_flags"] = af

cmd = build_bactopia_cmd(params)

st.caption(f"Profile: {params['profile']} | Outdir: {params['outdir']}")
st.caption(
    f"HOME={os.environ.get('HOME')} | "
    f"NXF_HOME={os.environ.get('NXF_HOME', '(not set)')}"
)
st.caption(
    f"BACTOPIA_ENV_PREFIX={os.environ.get('BACTOPIA_ENV_PREFIX', '(not set)')}"
)
st.code(cmd, language="bash")

# ============================= Pre-run validation =============================

def preflight_validate(params: dict, fofn_path: str) -> list[str]:
    """
    Validate the configuration before execution.

    Args:
        params (dict): Run parameters.
        fofn_path (str): Path to the samples.txt file.

    Returns:
        list[str]: A list of error messages. Empty if validation passes.
    """
    errs: list[str] = []

    if not utils.docker_available():
        errs.append(
            "Docker is not available in PATH. "
            "This app runs Bactopia only with '-profile docker', so Docker is mandatory."
        )

    datasets = params.get("datasets")
    if datasets and not pathlib.Path(datasets).exists():
        errs.append(f"Path does not exist: datasets = {datasets}")

    if not pathlib.Path(fofn_path).is_file():
        errs.append(
            f"FOFN not found: {fofn_path}.\n"
            "Generate the FOFN in 'Generate FOFN' (button '🔎 Scan base folder and build FOFN') before running."
        )

    return errs


_errors = preflight_validate(params, fofn_out)

if _errors:
    st.error("Configuration errors detected. Fix them before running:")
    for e in _errors:
        st.markdown(f"- {e}")

# ============================= Run / Clean buttons =============================

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    start_main = st.button(
        "▶️ Run (async)",
        key="btn_main_start",
        disabled=st.session_state.get("main_running", False),
    )
with col2:
    stop_main = st.button(
        "⏹️ Stop",
        key="btn_main_stop",
        disabled=not st.session_state.get("main_running", False),
    )
with col3:
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.checkbox("Confirm", value=False, key="confirm_clean")
    with c2:
        st.checkbox("Keep logs (-k)", value=False, key="clean_keep_logs")
    with c3:
        st.checkbox("All runs", value=False, key="clean_all_runs")
    clean_clicked = st.button(
        "🧹 Clean environment",
        key="btn_clean_main",
        disabled=not st.session_state.get("confirm_clean", False),
    )

status_box_main = st.empty()
report_zone_main = st.empty()
log_container_main = st.empty()

# --- Cleaning runs ---
if clean_clicked:
    if st.session_state.get("main_running", False):
        utils.request_stop_ns("main")
        time.sleep(0.8)

    # Clean/log from the same outdir used in runs
    launch_dir = pathlib.Path(st.session_state.get("outdir", DEFAULT_OUTDIR)).expanduser().resolve()
    launch_dir.mkdir(parents=True, exist_ok=True)
    utils.ensure_project_nxf_dir(launch_dir)
    utils.ensure_nxf_home()

    if not utils.nextflow_available():
        st.error("Nextflow not found (neither in PATH nor in BACTOPIA_ENV_PREFIX).")
    else:
        all_runs = st.session_state.get("clean_all_runs", False)
        keep_logs = st.session_state.get("clean_keep_logs", False)

        try:
            nf_bin = utils.get_nextflow_bin()
            rc, stdout, stderr = utils.run_cmd(
                [nf_bin, "log", "-q"],
                cwd=str(launch_dir),
            )
            raw_names = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
            seen = set()
            run_names = []
            for rn in raw_names:
                if rn not in seen:
                    seen.add(rn)
                    run_names.append(rn)

            if not run_names:
                st.info("No runs found by `nextflow log`.")
            else:
                targets = [run_names[-1]] if not all_runs else list(reversed(run_names))
                failures = []
                cleaned = 0
                for rn in targets:
                    cmdc = [nf_bin, "clean", "-f"] + (["-k"] if keep_logs else []) + [rn]
                    st.code(" ".join(shlex.quote(x) for x in cmdc), language="bash")
                    rc_clean, stdout_clean, stderr_clean = utils.run_cmd(
                        cmdc,
                        cwd=str(launch_dir),
                    )
                    if rc_clean == 0:
                        cleaned += 1
                    else:
                        msg = (stderr_clean or stdout_clean or "").strip()
                        failures.append((rn, msg))

                if cleaned and not failures:
                    if all_runs:
                        st.success(f"Cleaned {cleaned} run(s).")
                    else:
                        st.success(f"Cleaned: {targets[0]}")
                elif cleaned and failures:
                    st.warning(f"Partial cleanup: {cleaned} ok, {len(failures)} failed.")
                else:
                    st.error(
                        "Failed to clean last run." if not all_runs else "Failed to clean all runs."
                    )

                for rn, msg in failures:
                    st.markdown(f"- **{rn}**")
                    if msg:
                        st.code(msg)

                if any("Missing cache index file" in (m or "") for _, m in failures):
                    st.warning(
                        "Some runs do not have a cache index (`.nextflow/cache`). "
                        "In these cases, `nextflow clean` cannot map `work/`. "
                        "If needed, you may manually/forcibly remove `work/` and `.nextflow/cache/` (irreversible)."
                    )
        except Exception as e:
            st.exception(e)

if stop_main:
    utils.request_stop_ns("main")
    status_box_main.warning("Stop requested…")

if start_main:
    if _errors:
        st.error("Run blocked by the validation errors above.")
    elif not utils.nextflow_available():
        st.error("Nextflow not found (neither in PATH nor in BACTOPIA_ENV_PREFIX).")
    else:
        try:
            full_cmd = cmd  # no stdbuf wrapper, use the command as built
            status_box_main.info("Running (async).")
            utils.start_async_runner_ns(full_cmd, "main")
        except Exception as e:
            st.error(f"Failed to start (async): {e}")

if st.session_state.get("main_running", False):
    utils.drain_log_queue_ns("main", tail_limit=200, max_pull=500)
    utils.render_log_box_ns("main")
    finished = utils.check_status_and_finalize_ns(
        "main",
        status_box_main,
        report_zone_main,
    )
    if not finished:
        time.sleep(0.3)
        utils._st_rerun()
else:
    utils.render_log_box_ns("main")

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
