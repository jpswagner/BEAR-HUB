# MERLIN.py — Species-specific Bactopia tools (via --wf)
# ---------------------------------------------------------------
# Standalone usage:
#   streamlit run MERLIN.py
#
# Within BEAR-HUB, this file is used as an additional page.
# ---------------------------------------------------------------

import os
import shlex
import time
import pathlib
import subprocess
import re
import shutil
import asyncio
import html
import threading
import hashlib
import fnmatch
from typing import List
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components

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


def _st_rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()


APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
# Aligned with BEAR-HUB: ~/BEAR_DATA/bactopia_out
DEFAULT_OUTDIR = str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").resolve())

# ===================== Nextflow via Bactopia conda env =====================

def bootstrap_bear_env_from_file():
    """
    If the user did not run `source .bear-hub.env` before starting Streamlit,
    try to load that file and populate key environment variables:

      - BEAR_HUB_ROOT / BEAR_HUB_BASEDIR
      - BACTOPIA_ENV_PREFIX
      - NXF_CONDA_EXE

    Rules:
      - If BACTOPIA_ENV_PREFIX already exists AND NXF_CONDA_EXE points to a valid binary,
        nothing is changed.
      - For NXF_CONDA_EXE: if it exists but is invalid, it will be overwritten.
      - For other variables: only set them if they do not already exist.
    """
    solver = os.environ.get("NXF_CONDA_EXE")
    if os.environ.get("BACTOPIA_ENV_PREFIX") and solver and os.path.exists(solver):
        return

    candidates: list[pathlib.Path] = []

    # If BEAR_HUB_ROOT is defined, use it as starting point
    env_root = os.environ.get("BEAR_HUB_ROOT")
    if env_root:
        candidates.append(pathlib.Path(env_root).expanduser() / ".bear-hub.env")

    # Default BEAR-HUB installation path
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
                    # Remove quotes if line is like: export VAR="..."
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

    if os.environ.get("BEAR_HUB_ROOT") and not os.environ.get("BEAR_HUB_BASEDIR"):
        os.environ["BEAR_HUB_BASEDIR"] = os.environ["BEAR_HUB_ROOT"]


# Try to load .bear-hub.env early
bootstrap_bear_env_from_file()

# Discover Nextflow inside the "bactopia" environment, if present
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


def which(cmd: str):
    from shutil import which as _which
    return _which(cmd)


def get_nextflow_bin() -> str:
    """
    Priority order for Nextflow binary:
      1) st.session_state['nextflow_bin']
      2) $NEXTFLOW_BIN
      3) BACTOPIA_ENV_PREFIX/bin/nextflow
      4) 'nextflow' in system PATH
    """
    v = (st.session_state.get("nextflow_bin") or "").strip()
    if v:
        return v
    v = (os.environ.get("NEXTFLOW_BIN") or "").strip()
    if v:
        return v
    if BACTOPIA_NEXTFLOW_BIN:
        return BACTOPIA_NEXTFLOW_BIN
    return "nextflow"


def nextflow_available() -> bool:
    """
    Check if there is a usable Nextflow binary.
    """
    if (st.session_state.get("nextflow_bin") or "").strip():
        return True
    if (os.environ.get("NEXTFLOW_BIN") or "").strip():
        return True
    if BACTOPIA_NEXTFLOW_BIN:
        return True
    return which("nextflow") is not None


def have_tool(name: str) -> bool:
    return which(name) is not None

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
    with st.popover(label):
        st.markdown(text)


def help_header(title_md: str, help_key: str, ratio=(4, 1)):
    c1, c2 = st.columns(ratio)
    with c1:
        st.markdown(title_md)
    with c2:
        help_popover("❓ Help", HELP[help_key])

# ============================= File explorer (popup) =============================

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


def _fs_browser_core(
    label: str,
    key: str,
    mode: str = "file",
    start: str | None = None,
    patterns: list[str] | None = None,
):
    """
    Core file browser:

    - Directory navigation (up, base, host).
    - Folder/file selection.
    - Optional pattern filtering (e.g.: *.tsv).
    """
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
        if st.button("🏠 Base", key=f"{key}_home"):
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
    st.markdown("**Directories**")
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


def path_picker(
    label: str,
    key: str,
    mode: str = "dir",
    start: str | None = None,
    patterns: list[str] | None = None,
    help: str | None = None,
):
    """
    Same pattern as in BACTOPIA-TOOLS:

    - Text field + "Browse…" button.
    - Opens a file browser in a dialog (`st.dialog`) when clicking "Browse…".
    - Dialog has "Use this path" and "Cancel" actions.
    """
    open_key = f"__open_{key}"
    cur_key = f"__picker_cur__{key}"

    if open_key not in st.session_state:
        st.session_state[open_key] = False

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
            st.session_state[open_key] = True
            try:
                hint = pathlib.Path(st.session_state.get(key) or start or os.getcwd())
                base = hint if hint.is_dir() else hint.parent
                st.session_state[cur_key] = str(base.expanduser().resolve())
            except Exception:
                st.session_state[cur_key] = str(
                    pathlib.Path(start or os.getcwd()).expanduser().resolve()
                )

    # Dialog-based popup (if available)
    if st.session_state.get(open_key, False) and hasattr(st, "dialog"):
        @st.dialog(label, width="large")
        def _dlg():
            _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                if st.button("✅ Use this path", key=f"use_{key}"):
                    if mode == "dir":
                        cur = pathlib.Path(st.session_state.get(cur_key, start or os.getcwd()))
                        st.session_state[key] = str(cur.expanduser().resolve())
                    st.session_state[open_key] = False
                    _st_rerun()
            with c_cancel:
                if st.button("Cancel", key=f"cancel_{key}"):
                    st.session_state[open_key] = False
                    _st_rerun()
        _dlg()

    # Inline fallback if st.dialog does not exist (older Streamlit)
    elif st.session_state.get(open_key, False):
        st.info(f"{label} (inline mode — fallback)")
        _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
        c_ok, c_cancel = st.columns(2)
        with c_ok:
            if st.button("✅ Use this path", key=f"use_inline_{key}"):
                if mode == "dir":
                    cur = pathlib.Path(st.session_state.get(cur_key, start or os.getcwd()))
                    st.session_state[key] = str(cur.expanduser().resolve())
                st.session_state[open_key] = False
                _st_rerun()
        with c_cancel:
            if st.button("Cancel", key=f"cancel_inline_{key}"):
                st.session_state[open_key] = False
                _st_rerun()

    return st.session_state.get(key) or ""

# ============================= Async execution utils =============================

def ensure_state_dir():
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)


ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(s: str) -> str:
    return ANSI_ESCAPE.sub("", s)


def _normalize_linebreaks(chunk: str) -> list[str]:
    """
    Normalize log output:
      - remove ANSI color/escape codes
      - adapt long lines into more readable breaks
    """
    if not chunk:
        return []
    chunk = _strip_ansi(chunk).replace("\r", "\n")
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    return [p.rstrip() for p in chunk.split("\n") if p.strip() != ""]


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
            "bash",
            "-lc",
            full_cmd,
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
    """
    Start an asynchronous runner:

      - ns = "species" (namespace for state)
      - full_cmd = complete bash command to execute
    """
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
    """
    Pull messages from the log queue into st.session_state,
    keeping only the last `tail_limit` lines.
    """
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


def render_log_box_ns(ns: str, height: int = 520):
    """
    Render a custom HTML "terminal" log box.
    """
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


def check_status_and_finalize_ns(ns: str, status_box):
    """
    Check if the async runner has finished and update visual status.
    """
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
            status_box.error(msg or f"Execution finished with code {rc}. Check the log below.")
    return finalized

# ============================= Bactopia helpers =============================

def discover_samples_from_outdir(outdir: str) -> List[str]:
    """
    Same logic as in BACTOPIA-TOOLS:

    - First, consider only directories containing 'main/' or 'tools/'.
    - If none match, use all non-administrative subdirectories as samples.
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
    Try to guess the base Bactopia directory using multiple candidates:

    1) Global BEAR-HUB outdir (st.session_state['outdir'])
    2) outdir/bactopia_out
    3) PROJECT_ROOT/bactopia_out
    4) APP_ROOT/bactopia_out
    5) ~/BEAR_DATA/bactopia_out (fallback)

    Choose the first one that has detectable samples.
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
    Create a temporary file for `--include`, with one sample per line.
    """
    ensure_state_dir()
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
    Build the Nextflow command for a specific species workflow (`--wf <tool>`):

      nextflow run bactopia/bactopia \
        -profile <profile> \
        --wf <tool> \
        --bactopia <outdir> \
        --include <include_file> \
        [--max_cpus ...] [--max_memory ...] [-resume] [extra...]
    """
    nf_bin = get_nextflow_bin()
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

bt_outdir = path_picker(
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
    request_stop_ns("species")
    status_box_species.warning("Stop requested…")

if start_species:
    if not nextflow_available():
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
                    start_async_runner_ns(full_cmd, "species")

# Live log update
if st.session_state.get("species_running", False):
    drain_log_queue_ns("species", tail_limit=500, max_pull=800)
    render_log_box_ns("species", height=520)
    finished = check_status_and_finalize_ns("species", status_box_species)
    if not finished:
        time.sleep(0.3)
        _st_rerun()
else:
    render_log_box_ns("species", height=520)

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
