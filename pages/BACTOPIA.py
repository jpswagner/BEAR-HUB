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

import os
import shlex
import time
import yaml
import pathlib
import subprocess
import re
import asyncio
import html
import threading
import fnmatch
import hashlib
from typing import List, Dict, Tuple
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components

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

# ============================= Basic helpers =============================

def _st_rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()


APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
PRESETS_FILE = APP_STATE_DIR / "presets.yaml"
DEFAULT_PRESET_NAME = "default"


def bootstrap_bear_env_from_file():
    """
    Try to load `.bear-hub.env` if the user didn't do `source .bear-hub.env`
    before starting Streamlit. This file is used to populate environment variables:
      - BEAR_HUB_ROOT
      - BEAR_HUB_BASEDIR (if missing)
      - BACTOPIA_ENV_PREFIX
      - NXF_CONDA_EXE

    Rules:
      - We skip loading if BACTOPIA_ENV_PREFIX is already set AND NXF_CONDA_EXE
        points to a valid binary.
      - For NXF_CONDA_EXE: if it exists but points to a non-existing path,
        it will be overwritten by the value from .bear-hub.env.
      - For the other variables, we only set them if they don't exist in os.environ.
    """
    # If we already have BACTOPIA_ENV_PREFIX and a valid NXF_CONDA_EXE, assume env is ready
    solver = os.environ.get("NXF_CONDA_EXE")
    if os.environ.get("BACTOPIA_ENV_PREFIX") and solver and os.path.exists(solver):
        return

    candidates: list[pathlib.Path] = []

    # If BEAR_HUB_ROOT exists, use it to locate .bear-hub.env
    env_root = os.environ.get("BEAR_HUB_ROOT")
    if env_root:
        candidates.append(pathlib.Path(env_root).expanduser() / ".bear-hub.env")

    # Fallback to ~/BEAR-HUB/.bear-hub.env (install_bear.sh default)
    candidates.append(pathlib.Path.home() / "BEAR-HUB" / ".bear-hub.env")

    for cfg in candidates:
        try:
            if not cfg.is_file():
                continue
            with cfg.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r'export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
                    if not m:
                        continue
                    var, value = m.group(1), m.group(2).strip()
                    # remove quotes if the line is export VAR="..."
                    if ((value.startswith('"') and value.endswith('"'))
                            or (value.startswith("'") and value.endswith("'"))):
                        value = value[1:-1]
                    if not var or not value:
                        continue

                    if var == "NXF_CONDA_EXE":
                        cur = os.environ.get("NXF_CONDA_EXE")
                        if (not cur) or (cur and not os.path.exists(cur)):
                            os.environ["NXF_CONDA_EXE"] = value
                    else:
                        if var not in os.environ:
                            os.environ[var] = value
            break
        except Exception:
            continue

    # If BEAR_HUB_ROOT was set via file but BEAR_HUB_BASEDIR was not,
    # use BEAR_HUB_ROOT as the default base.
    if os.environ.get("BEAR_HUB_ROOT") and not os.environ.get("BEAR_HUB_BASEDIR"):
        os.environ["BEAR_HUB_BASEDIR"] = os.environ["BEAR_HUB_ROOT"]


# Attempt to load .bear-hub.env early
bootstrap_bear_env_from_file()

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

st.session_state.setdefault("outdir", DEFAULT_OUTDIR)

# ============================= Bactopia / Nextflow (env prefix) =============================

BACTOPIA_ENV_PREFIX = os.environ.get("BACTOPIA_ENV_PREFIX")
BACTOPIA_NEXTFLOW_BIN: str | None = None

if BACTOPIA_ENV_PREFIX:
    try:
        _bact_env = pathlib.Path(BACTOPIA_ENV_PREFIX).expanduser().resolve()
        _cand_nf = _bact_env / "bin" / "nextflow"
        if _cand_nf.is_file() and os.access(_cand_nf, os.X_OK):
            BACTOPIA_NEXTFLOW_BIN = str(_cand_nf)
    except Exception:
        BACTOPIA_NEXTFLOW_BIN = None


# ===================== Nextflow: ensure writable NXF_HOME =====================

def ensure_nxf_home() -> str | None:
    """
    Ensure there is a writable NXF_HOME to avoid cache/history issues.
    Preference:
      1) $BEAR_HUB_OUTDIR/.nextflow (if set)
      2) $BEAR_HUB_BASEDIR/.nextflow (if set)
      3) DEFAULT_OUTDIR/.nextflow
      4) $HOME/.nextflow
    """
    existing = os.environ.get("NXF_HOME")
    if existing:
        try:
            pathlib.Path(existing).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return existing

    base_env = os.getenv("BEAR_HUB_OUTDIR") or os.getenv("BEAR_HUB_BASEDIR")
    if base_env:
        base = pathlib.Path(base_env).expanduser().resolve()
    else:
        base = pathlib.Path(DEFAULT_OUTDIR).expanduser().resolve()

    nxf_home_path = base / ".nextflow"
    try:
        nxf_home_path.mkdir(parents=True, exist_ok=True)
        os.environ["NXF_HOME"] = str(nxf_home_path)
        return str(nxf_home_path)
    except Exception:
        try:
            home_nxf = pathlib.Path.home() / ".nextflow"
            home_nxf.mkdir(parents=True, exist_ok=True)
            os.environ["NXF_HOME"] = str(home_nxf)
            return str(home_nxf)
        except Exception:
            return None


def ensure_project_nxf_dir(base: str | pathlib.Path | None = None) -> str | None:
    """
    Ensure there is a `.nextflow` directory where Nextflow is executed,
    to avoid the error:
       ERROR ~ .nextflow/history.lock (No such file or directory)
    """
    try:
        base_path = pathlib.Path(base) if base is not None else pathlib.Path.cwd()
        proj_nxf = base_path / ".nextflow"
        proj_nxf.mkdir(parents=True, exist_ok=True)
        return str(proj_nxf)
    except Exception:
        return None


# Guarantee NXF_HOME on module load
ensure_nxf_home()

# ============================= Utils =============================

def ensure_state_dir():
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)


def which(cmd: str):
    from shutil import which as _which
    return _which(cmd)


def docker_available():
    return which("docker") is not None


def get_nextflow_bin() -> str:
    """
    Return the Nextflow binary to use:
    - if BACTOPIA_ENV_PREFIX is set and has bin/nextflow, use that;
    - otherwise, use 'nextflow' from system PATH.
    """
    return BACTOPIA_NEXTFLOW_BIN or "nextflow"


def nextflow_available():
    if BACTOPIA_NEXTFLOW_BIN:
        return True
    return which("nextflow") is not None


def run_cmd(cmd: str | List[str], cwd: str | None = None) -> tuple[int, str, str]:
    if isinstance(cmd, list):
        shell_cmd = " ".join(shlex.quote(x) for x in cmd)
    else:
        shell_cmd = cmd
    try:
        res = subprocess.run(
            ["bash", "-c", shell_cmd],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        return res.returncode, res.stdout or "", res.stderr or ""
    except Exception as e:
        return 1, "", f"Failed to execute: {e}"

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
    "fastp_n", "fastp_u", "fastp_cut_front", "fastp_cut_tail", "fastp_cut_meanq", "fastp_cut_win",
    "fastp_detect_adapter_pe", "fastp_poly_g", "fastp_extra",
    # Unicycler
    "unicycler_mode", "unicycler_min_len", "unicycler_extra",
    # Extra params and reports
    "extra_params", "with_report", "with_timeline", "with_trace",
}


def load_presets():
    ensure_state_dir()
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_presets(presets: dict):
    ensure_state_dir()
    with open(PRESETS_FILE, "w", encoding="utf-8") as fh:
        yaml.safe_dump(presets, fh, sort_keys=True, allow_unicode=True)


def _snapshot_current_state() -> dict:
    snap = {}
    for k in PRESET_KEYS_ALLOWLIST:
        if k in st.session_state:
            snap[k] = st.session_state[k]
    return snap


def _apply_dict_to_state(values: dict):
    for k, v in (values or {}).items():
        if k in PRESET_KEYS_ALLOWLIST:
            st.session_state[k] = v


def apply_preset_before_widgets():
    pending = st.session_state.pop("__pending_preset_values", None)
    if pending:
        _apply_dict_to_state(pending)
        st.session_state["__preset_msg"] = st.session_state.get("__preset_msg") or "Preset applied."


def _cb_stage_apply_preset():
    name = st.session_state.get("__preset_to_load")
    if not name or name == "(none)":
        return
    presets = load_presets()
    st.session_state["__pending_preset_values"] = presets.get(name, {})
    st.session_state["__preset_msg"] = f"Preset staged: {name} (applied on this reload)"


def _cb_save_preset():
    name = (st.session_state.get("__preset_save_name") or "").strip() or DEFAULT_PRESET_NAME
    name = re.sub(r"\s+", "_", name)
    presets = load_presets()
    presets[name] = _snapshot_current_state()
    save_presets(presets)
    st.session_state["__preset_msg"] = f"Preset saved: {name}"


def _cb_delete_preset():
    name = st.session_state.get("__preset_to_load")
    if not name or name == "(none)":
        return
    presets = load_presets()
    if name in presets:
        del presets[name]
        save_presets(presets)
        st.session_state["__preset_msg"] = f"Preset deleted: {name}"


def render_presets_sidebar():
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

# ============================= File explorer (inline + pop-up) =============================

def _safe_id(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


def _list_dir(cur: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    try:
        entries = list(cur.iterdir())
    except Exception:
        entries = []
    dirs = [p for p in entries if p.is_dir()]
    files = [p for p in entries if p.is_file()]
    dirs.sort(key=lambda p: p.name.lower())
    files.sort(key=lambda p: p.name.lower())
    return dirs, files


def _fs_browser_core(label: str, key: str, mode: str = "file",
                     start: str | None = None, patterns: list[str] | None = None):
    base_start = start or st.session_state.get(key) or os.getcwd()
    cur_key = f"__picker_cur__{key}"
    try:
        cur = pathlib.Path(st.session_state.get(cur_key, base_start)).expanduser().resolve()
    except Exception:
        cur = pathlib.Path(base_start).expanduser().resolve()

    def set_cur(p: pathlib.Path):
        st.session_state[cur_key] = str(p.expanduser().resolve())

    hostfs_root = os.getenv("HOSTFS_ROOT", "/hostfs")

    c_up, c_home, c_host, c_path, c_pick = st.columns([0.9, 0.9, 0.9, 6, 2])

    with c_up:
        if st.button("⬆️ Up", key=f"{key}_up"):
            parent = cur.parent if cur.parent != cur else cur
            set_cur(parent)
            _st_rerun()

    with c_home:
        home_base = pathlib.Path(start or pathlib.Path.home())
        if st.button("🏠 Home", key=f"{key}_home"):
            set_cur(home_base)
            _st_rerun()

    with c_host:
        if os.path.exists(hostfs_root):
            if st.button("🖥 Host", key=f"{key}_host"):
                set_cur(pathlib.Path(hostfs_root))
                _st_rerun()

    with c_path:
        st.caption(str(cur))

    with c_pick:
        if mode == "dir":
            if st.button("Choose", key=f"{key}_choose_dir"):
                st.session_state[key] = str(cur)

    dirs, files = _list_dir(cur)
    st.markdown("**Folders**")
    dcols = st.columns(2)
    for i, d in enumerate(dirs):
        did = _safe_id(str(d))
        if dcols[i % 2].button("📁 " + d.name, key=f"{key}_d_{did}"):
            set_cur(d)
            _st_rerun()

    if mode == "file":
        if patterns:
            files = [f for f in files if any(fnmatch.fnmatch(f.name, pat) for pat in patterns)]
        st.markdown("**Files**")
        for f in files:
            fid = _safe_id(str(f))
            if st.button("📄 " + f.name, key=f"{key}_f_{fid}"):
                st.session_state[key] = str(f.resolve())
                st.session_state[f"__open_{key}"] = False
                _st_rerun()


def path_picker(label: str, key: str, mode: str = "dir",
                start: str | None = None, patterns: list[str] | None = None, help: str | None = None):
    col1, col2 = st.columns([7, 2])
    with col1:
        val = st.text_input(label, value=st.session_state.get(key, start or ""), key=key, help=help)
        try:
            if val:
                val_abs = str(pathlib.Path(val).expanduser().resolve())
                if val_abs != val:
                    st.session_state[key] = val_abs
        except Exception:
            pass
    with col2:
        if st.button("Browse…", key=f"open_{key}"):
            st.session_state[f"__open_{key}"] = True
            try:
                hint = pathlib.Path(st.session_state.get(key) or start or os.getcwd())
                st.session_state[f"__picker_cur__{key}"] = str(
                    (hint if hint.is_dir() else hint.parent).expanduser().resolve()
                )
            except Exception:
                st.session_state[f"__picker_cur__{key}"] = str(
                    pathlib.Path(start or os.getcwd()).expanduser().resolve()
                )

    if st.session_state.get(f"__open_{key}", False) and hasattr(st, "dialog"):
        @st.dialog(label, width="large")
        def _dlg():
            _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                if st.button("✅ Use this path", key=f"use_{key}"):
                    if mode == "dir":
                        cur = pathlib.Path(st.session_state.get(f"__picker_cur__{key}", start or os.getcwd()))
                        st.session_state[key] = str(cur.expanduser().resolve())
                    st.session_state[f"__open_{key}"] = False
                    _st_rerun()
            with c_cancel:
                if st.button("Cancel", key=f"cancel_{key}"):
                    st.session_state[f"__open_{key}"] = False
                    _st_rerun()
        _dlg()
    elif st.session_state.get(f"__open_{key}", False):
        st.info(f"{label} (inline mode)")
        _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
        if st.button("✅ Use this path", key=f"use_inline_{key}"):
            if mode == "dir":
                cur = pathlib.Path(st.session_state.get(f"__picker_cur__{key}", start or os.getcwd()))
                st.session_state[key] = str(cur.expanduser().resolve())
            st.session_state[f"__open_{key}"] = False
            _st_rerun()

    return st.session_state.get(key) or ""

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
    for ext in [".fastq.gz", ".fq.gz", ".fastq", ".fq", ".fna.gz", ".fa.gz", ".fasta.gz", ".fna", ".fa", ".fasta"]:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _infer_root_and_tag(path: pathlib.Path) -> Tuple[str, str]:
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
    s = str(p.as_posix()).lower()
    return any(x in s for x in ["ont", "nanopore", "minion", "promethion", "fastq_pass", "guppy"])


def _collect_files(base: pathlib.Path, patterns: List[str], recursive: bool) -> List[pathlib.Path]:
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

# ============================= Async runner =============================

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(s: str) -> str:
    return ANSI_ESCAPE.sub("", s)


def _normalize_linebreaks(chunk: str) -> list[str]:
    if not chunk:
        return []
    chunk = _strip_ansi(chunk).replace("\r", "\n")
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    parts = [p.rstrip() for p in chunk.split("\n") if p.strip() != ""]
    return parts


async def _async_read_stream(stream, log_q: Queue, stop_event: threading.Event):
    while True:
        line = await stream.readline()
        if not line:
            break
        s = line.decode(errors="replace")
        for sub in _normalize_linebreaks(s):
            log_q.put(sub)
        if stop_event.is_set():
            break


async def _async_exec(full_cmd: str, log_q: Queue, status_q: Queue, stop_event: threading.Event):
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        status_q.put(("error", f"Failed to start process: {e}"))
        return
    t_out = asyncio.create_task(_async_read_stream(proc.stdout, log_q, stop_event))
    t_err = asyncio.create_task(_async_read_stream(proc.stderr, log_q, stop_event))
    while True:
        if stop_event.is_set():
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
            except ProcessLookupError:
                pass
            break
        if proc.returncode is not None:
            break
        await asyncio.sleep(0.1)
    try:
        await asyncio.gather(t_out, t_err)
    except Exception:
        pass
    rc = await proc.wait()
    status_q.put(("rc", rc))


def _thread_entry(full_cmd: str, log_q: Queue, status_q: Queue, stop_event: threading.Event):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_exec(full_cmd, log_q, status_q, stop_event))
    finally:
        loop.close()


def start_async_runner_ns(full_cmd: str, ns: str):
    log_q = Queue()
    status_q = Queue()
    stop_event = threading.Event()
    th = threading.Thread(
        target=_thread_entry,
        args=(full_cmd, log_q, status_q, stop_event),
        daemon=True,
    )
    th.start()
    st.session_state[f"{ns}_running"] = True
    st.session_state[f"{ns}_log_q"] = log_q
    st.session_state[f"{ns}_status_q"] = status_q
    st.session_state[f"{ns}_stop_event"] = stop_event
    st.session_state[f"{ns}_thread"] = th
    st.session_state[f"{ns}_live_log"] = []


def request_stop_ns(ns: str):
    ev = st.session_state.get(f"{ns}_stop_event")
    if ev and not ev.is_set():
        ev.set()


def drain_log_queue_ns(ns: str, tail_limit: int = 200, max_pull: int = 500):
    q: Queue = st.session_state.get(f"{ns}_log_q")
    if not q:
        return
    buf = st.session_state.get(f"{ns}_live_log", [])
    pulled = 0
    while pulled < max_pull:
        try:
            line = q.get_nowait()
        except Empty:
            break
        buf.append(line)
        pulled += 1
    if len(buf) > tail_limit:
        buf[:] = buf[-tail_limit:]
    st.session_state[f"{ns}_live_log"] = buf


def render_log_box_ns(ns: str, height: int = 560):
    lines = st.session_state.get(f"{ns}_live_log", [])
    content = html.escape("\n".join(lines)) if lines else ""
    components.html(
        f"""
    <div id="logbox_{ns}" style=
        "
        width:100%; height:{height-40}px; margin:0 auto; padding:12px;
        overflow-y:auto; overflow-x:auto; background:#0b0b0b; color:#e6e6e6;
        border-radius:10px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
        font-size:13px; line-height:1.35;">
      <pre style="margin:0; white-space: pre;">{content or "&nbsp;"}</pre>
    </div>
    <script>const el=document.getElementById("logbox_{ns}"); if(el){{el.scrollTop=el.scrollHeight;}}</script>
    """,
        height=height,
        scrolling=False,
    )


def check_status_and_finalize_ns(outdir: str, ns: str, status_box, report_zone):
    sq: Queue = st.session_state.get(f"{ns}_status_q")
    if not sq:
        return False
    finalized = False
    msg = None
    rc = None
    try:
        while True:
            kind, payload = sq.get_nowait()
            if kind == "error":
                msg = payload
                finalized = True
                rc = -1
            elif kind == "rc":
                rc = int(payload)
                finalized = True
    except Empty:
        pass
    if finalized:
        st.session_state[f"{ns}_running"] = False
        st.session_state[f"{ns}_thread"] = None
        st.session_state[f"{ns}_stop_event"] = None
        if rc == 0:
            status_box.success("Finished successfully.")
        else:
            status_box.error(msg or f"Run finished with code {rc}. See the log below.")
    return finalized

# ============================= Sidebar =============================

ICON_PATH = PROJECT_ROOT / "static" / "bear-hub-icon.png"

with st.sidebar:
    st.markdown("---")
    st.header("Environment")
    nf_ok = nextflow_available()
    docker_ok = docker_available()
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
        if BACTOPIA_NEXTFLOW_BIN:
            st.caption(f"Nextflow via Bactopia env: `{BACTOPIA_NEXTFLOW_BIN}`")
        else:
            st.caption("Nextflow found via system PATH.")

    if not docker_ok:
        st.error(
            "Docker is not available. Install and enable Docker before running Bactopia.",
            icon="⚠️",
        )

    if BACTOPIA_ENV_PREFIX:
        st.caption(f"BACTOPIA_ENV_PREFIX: `{BACTOPIA_ENV_PREFIX}`")

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
    base_dir = path_picker(
        "Base folder with FASTQs/FASTAs",
        key="fofn_base",
        mode="dir",
        start=base_default,
        help=(
            "In local conda installs, use normal paths (e.g., /mnt/HD/...). "
            "If running inside Docker, your host filesystem may be mounted under /hostfs "
            "(e.g., /hostfs/mnt/HD/...)."
        ),
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
        gsize_in = st.text_input(
            "genome_size (optional)",
            value=st.session_state.get("fofn_gsize", "0"),
            key="fofn_gsize",
        )
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

# ============================= Main parameters =============================

st.subheader("Main parameters")
with st.expander("Global parameters", expanded=False):
    colA, colB = st.columns(2)
    with colA:
        # Force '-profile docker' always
        st.session_state["profile"] = "docker"
        st.text_input(
            "Profile (-profile)",
            value="docker",
            key="profile",
            disabled=True,
            help="This app always uses '-profile docker' for Bactopia.",
        )

        outdir = path_picker(
            "Outdir (results root)",
            key="outdir",
            mode="dir",
            start=DEFAULT_OUTDIR,
            help="Folder where Nextflow/Bactopia will write output.",
        )
        datasets = path_picker(
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

# ============================= FASTP / Unicycler =============================

FASTP_HELP_MD = """
# ℹ️ fastp — explanation of parameters shown in the UI

This panel builds the `--fastp_opts` string used by Bactopia. Main options:

- `-3` : enable trimming at the 3' end (read tail).
- `-5` : enable trimming at the 5' end (read start).
- `-M <int>` : minimum average quality of the sliding window.
- `-W <int>` : window size for average quality.
- `-q <int>` : minimum quality for a base to be considered "good".
- `-l <int>` : minimum read length after trimming.
- `-n <int>` : maximum number of Ns in a read.
- `-u <int>` : maximum percentage of bases below given quality.
- `--cut_front` / `--cut_tail` : dynamic trimming at read ends.
- `--cut_mean_quality <int>` : minimum quality in the cutting window.
- `--cut_window_size <int>` : window size for dynamic trimming.
- `--detect_adapter_for_pe` : automatic adapter detection in PE.
- `-g` : enable polyG tail trimming.

The "Advanced extra (append)" text field lets you add any extra fastp flags
that are not explicitly mapped in the interface.
"""

st.subheader("FASTP / Unicycler settings", help=FASTP_HELP_MD)

with st.expander("fastp options", expanded=False):
    fastp_mode = st.radio(
        "Mode",
        ["Simple (recommended)", "Advanced (full line)"],
        index=0,
        key="fastp_mode",
        horizontal=True,
    )
    if fastp_mode.startswith("Simple"):
        topA, topB, topC = st.columns(3)
        with topA:
            st.checkbox("Enable 3’ (-3)", value=True, key="fastp_dash3")
        with topB:
            st.slider("-M (min window avg quality)", 0, 40, 20, 1, key="fastp_M")
        with topC:
            st.slider("-W (window size)", 1, 50, 5, 1, key="fastp_W")

        st.markdown("**Additional options (optional)**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.checkbox("Enable 5’ (-5)", value=False, key="fastp_enable_5prime")
            st.checkbox("Detect adapter in PE", value=False, key="fastp_detect_adapter_pe")
        with c2:
            st.checkbox("Quality (-q)", value=False, key="fastp_q_enable")
            if st.session_state.get("fastp_q_enable"):
                st.slider("Value for -q", 0, 40, 20, 1, key="fastp_q")
        with c3:
            st.checkbox("Min length (-l)", value=False, key="fastp_l_enable")
            if st.session_state.get("fastp_l_enable"):
                st.slider("Value for -l", 0, 500, 15, 1, key="fastp_l")
        with c4:
            st.number_input("Max Ns (-n)", min_value=0, max_value=10, value=0, step=1, key="fastp_n")
            st.number_input("Max % low qual (-u)", min_value=0, max_value=100, value=0, step=1, key="fastp_u")

        st.markdown("**Directed cuts (cut_*)**")
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            st.checkbox("--cut_front", value=False, key="fastp_cut_front")
        with cc2:
            st.checkbox("--cut_tail", value=False, key="fastp_cut_tail")
        with cc3:
            st.number_input("cut_mean_quality", min_value=0, max_value=40, value=20, step=1, key="fastp_cut_meanq")
        with cc4:
            st.number_input("cut_window_size", min_value=1, max_value=100, value=4, step=1, key="fastp_cut_win")

        st.checkbox("polyG (-g)", value=False, key="fastp_poly_g")
        fastp_extra = st.text_input(
            "Advanced extra (append)",
            value=st.session_state.get("fastp_extra", ""),
            key="fastp_extra",
        )

        parts = []
        if st.session_state.get("fastp_dash3", True):
            parts.append("-3")
        if st.session_state.get("fastp_enable_5prime"):
            parts.append("-5")
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
        if st.session_state.get("fastp_cut_front"):
            parts.append("--cut_front")
        if st.session_state.get("fastp_cut_tail"):
            parts.append("--cut_tail")
        if st.session_state.get("fastp_cut_front") or st.session_state.get("fastp_cut_tail"):
            parts += ["--cut_mean_quality", str(st.session_state.get("fastp_cut_meanq", 20))]
            parts += ["--cut_window_size", str(st.session_state.get("fastp_cut_win", 4))]
        if st.session_state.get("fastp_detect_adapter_pe"):
            parts.append("--detect_adapter_for_pe")
        if st.session_state.get("fastp_poly_g"):
            parts.append("-g")
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

with st.expander("Unicycler options", expanded=False):
    st.radio("Mode", ["conservative", "normal", "bold"], index=1, key="unicycler_mode")
    st.number_input("min_fasta_length", 0, 100000, 1000, 100, key="unicycler_min_len")
    st.text_input(
        "Extra (append)",
        value=st.session_state.get("unicycler_extra", ""),
        key="unicycler_extra",
    )
    uni_parts = ["--mode", st.session_state.get("unicycler_mode", "normal")]
    if st.session_state.get("unicycler_min_len", 1000):
        uni_parts += ["--min_fasta_length", str(int(st.session_state["unicycler_min_len"]))]
    if (st.session_state.get("unicycler_extra") or "").strip():
        uni_parts.append(st.session_state["unicycler_extra"].strip())
    unicycler_opts_value = " ".join(uni_parts)
    st.caption(f"unicycler_opts: `{unicycler_opts_value}`")

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
    # This app enforces '-profile docker' (container execution)
    profile = params.get("profile") or "docker"
    outdir = params.get("outdir", DEFAULT_OUTDIR)
    datasets = params.get("datasets")
    fastp_opts = params.get("fastp_opts")
    unicycler_opts = params.get("unicycler_opts")
    extra = params.get("extra_params")
    resume = params.get("resume", True)
    threads = params.get("threads")
    memory = params.get("memory")
    with_report = params.get("with_report")
    with_timeline = params.get("with_timeline")
    with_trace = params.get("with_trace")

    # Ensure outdir exists and has its own .nextflow/
    outdir_path = pathlib.Path(outdir).expanduser().resolve()
    outdir_path.mkdir(parents=True, exist_ok=True)
    ensure_project_nxf_dir(outdir_path)
    ensure_nxf_home()

    nf_bin = get_nextflow_bin()

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
    "resume": st.session_state.get("resume", True),
    "threads": st.session_state.get("threads") or None,
    "memory": (f"{st.session_state.get('memory_gb')} GB" if st.session_state.get("memory_gb") else None),
    "with_report": st.session_state.get("with_report", True),
    "with_timeline": st.session_state.get("with_timeline", True),
    "with_trace": st.session_state.get("with_trace", True),
}
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
    errs: list[str] = []

    if not docker_available():
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
        request_stop_ns("main")
        time.sleep(0.8)

    # Clean/log from the same outdir used in runs
    launch_dir = pathlib.Path(st.session_state.get("outdir", DEFAULT_OUTDIR)).expanduser().resolve()
    launch_dir.mkdir(parents=True, exist_ok=True)
    ensure_project_nxf_dir(launch_dir)
    ensure_nxf_home()

    if not nextflow_available():
        st.error("Nextflow not found (neither in PATH nor in BACTOPIA_ENV_PREFIX).")
    else:
        all_runs = st.session_state.get("clean_all_runs", False)
        keep_logs = st.session_state.get("clean_keep_logs", False)

        try:
            nf_bin = get_nextflow_bin()
            log_res = subprocess.run(
                [nf_bin, "log", "-q"],
                cwd=str(launch_dir),
                text=True,
                capture_output=True,
                check=False,
            )
            raw_names = [ln.strip() for ln in (log_res.stdout or "").splitlines() if ln.strip()]
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
                    res = subprocess.run(
                        cmdc,
                        cwd=str(launch_dir),
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    if res.returncode == 0:
                        cleaned += 1
                    else:
                        msg = (res.stderr or res.stdout or "").strip()
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
    request_stop_ns("main")
    status_box_main.warning("Stop requested…")

if start_main:
    if _errors:
        st.error("Run blocked by the validation errors above.")
    elif not nextflow_available():
        st.error("Nextflow not found (neither in PATH nor in BACTOPIA_ENV_PREFIX).")
    else:
        try:
            full_cmd = cmd  # no stdbuf wrapper, use the command as built
            status_box_main.info("Running (async).")
            start_async_runner_ns(full_cmd, "main")
        except Exception as e:
            st.error(f"Failed to start (async): {e}")

if st.session_state.get("main_running", False):
    drain_log_queue_ns("main", tail_limit=200, max_pull=500)
    render_log_box_ns("main")
    finished = check_status_and_finalize_ns(
        params.get("outdir", DEFAULT_OUTDIR),
        "main",
        status_box_main,
        report_zone_main,
    )
    if not finished:
        time.sleep(0.3)
        _st_rerun()
else:
    render_log_box_ns("main")

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