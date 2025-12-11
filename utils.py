"""
Utility functions for BEAR-HUB.

This module provides shared utilities for the BEAR-HUB Streamlit application,
including:
- File system browsing and path selection.
- System checks (Nextflow, Docker).
- Directory management (state dirs, Nextflow homes).
- Async execution of shell commands with log streaming.
- Environment variable loading.
"""

import os
import shlex
import time
import pathlib
import subprocess
import re
import asyncio
import html
import threading
import hashlib
import fnmatch
from typing import List, Tuple
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components

# ============================= Constants =============================

APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# ============================= Environment & System Checks =============================

def which(cmd: str) -> str | None:
    """
    Locate a command in the user's PATH.

    Args:
        cmd (str): The name of the command to search for.

    Returns:
        str or None: The full path to the command if found, else None.
    """
    from shutil import which as _which
    return _which(cmd)

def env_badge(label: str, ok: bool) -> str:
    """
    Generate a simple badge string indicating status.

    Args:
        label (str): The label for the badge (e.g., "Docker").
        ok (bool): True if the status is OK (green check), False otherwise (red X).

    Returns:
        str: A formatted string with an emoji and the label.
    """
    return f"{'✅' if ok else '❌'} {label}"

def docker_available() -> bool:
    """
    Check if Docker is available in the system PATH.

    Returns:
        bool: True if 'docker' executable is found, False otherwise.
    """
    return which("docker") is not None

def get_nextflow_bin() -> str:
    """
    Return the Nextflow binary path to use.

    Checks environment variables and session state in a specific order:
    1. st.session_state['nextflow_bin']
    2. os.environ['NEXTFLOW_BIN']
    3. BACTOPIA_ENV_PREFIX/bin/nextflow (if available)
    4. System PATH 'nextflow'

    Returns:
        str: The path to the Nextflow binary.
    """
    v = (st.session_state.get("nextflow_bin") or "").strip()
    if v:
        return v
    v = (os.environ.get("NEXTFLOW_BIN") or "").strip()
    if v:
        return v

    # Check for Bactopia env prefix
    bactopia_env = os.environ.get("BACTOPIA_ENV_PREFIX")
    if bactopia_env:
        try:
            _bact_env = pathlib.Path(bactopia_env).expanduser().resolve()
            _cand_nf = _bact_env / "bin" / "nextflow"
            if _cand_nf.is_file() and os.access(_cand_nf, os.X_OK):
                return str(_cand_nf)
        except Exception:
            pass

    return "nextflow"

def nextflow_available() -> bool:
    """
    Check if Nextflow is available.

    Returns:
        bool: True if Nextflow is configured or in PATH, False otherwise.
    """
    nf_bin = get_nextflow_bin()
    if nf_bin != "nextflow":
        return True
    return which("nextflow") is not None

def bootstrap_bear_env_from_file():
    """
    Load environment variables from `.bear-hub.env`.

    This function attempts to load configuration from `.bear-hub.env` if
    key variables (like BACTOPIA_ENV_PREFIX) are missing. It looks in
    `BEAR_HUB_ROOT` or standard installation paths.

    It sets:
      - BEAR_HUB_ROOT
      - BEAR_HUB_BASEDIR
      - BACTOPIA_ENV_PREFIX
      - NXF_CONDA_EXE (if valid)
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

# ============================= Directory Management =============================

def ensure_state_dir():
    """Create the application state directory if it doesn't exist."""
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)

def ensure_nxf_home(default_outdir: str | None = None) -> str | None:
    """
    Ensure there is a writable NXF_HOME to avoid cache/history issues.

    Nextflow requires a writable home directory for caching and history. This function
    checks or creates `NXF_HOME` in order of preference:
      1. $BEAR_HUB_OUTDIR/.nextflow
      2. $BEAR_HUB_BASEDIR/.nextflow
      3. DEFAULT_OUTDIR/.nextflow
      4. $HOME/.nextflow

    Args:
        default_outdir (str | None): Optional default output directory to check.

    Returns:
        str | None: The path to the writable NXF_HOME, or None if creation failed.
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
    elif default_outdir:
        base = pathlib.Path(default_outdir).expanduser().resolve()
    else:
        # Fallback to CWD if nothing else is available
        base = pathlib.Path.cwd()

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
    Ensure a `.nextflow` directory exists in the project base.

    This prevents the "No such file or directory" error for `.nextflow/history.lock`
    when Nextflow tries to write execution history.

    Args:
        base (str | pathlib.Path | None): The base directory for execution.
            Defaults to current working directory.

    Returns:
        str | None: The path to the `.nextflow` directory, or None on failure.
    """
    try:
        base_path = pathlib.Path(base) if base is not None else pathlib.Path.cwd()
        proj_nxf = base_path / ".nextflow"
        proj_nxf.mkdir(parents=True, exist_ok=True)
        return str(proj_nxf)
    except Exception:
        return None

# ============================= File Browser =============================

def _safe_id(s: str) -> str:
    """Generate a short hash ID for a string (safe for DOM IDs)."""
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


def _list_dir(cur: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """
    List directories and files in a given path.

    Args:
        cur (pathlib.Path): The directory to list.

    Returns:
        tuple: A tuple containing sorted lists of subdirectories and files.
    """
    try:
        entries = list(cur.iterdir())
    except Exception:
        entries = []
    dirs = [p for p in entries if p.is_dir()]
    files = [p for p in entries if p.is_file()]
    dirs.sort(key=lambda p: p.name.lower())
    files.sort(key=lambda p: p.name.lower())
    return dirs, files

def _st_rerun():
    """
    Trigger a rerun of the Streamlit script.

    Uses `st.rerun()` if available (newer Streamlit), otherwise falls back
    to `st.experimental_rerun()`.
    """
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()

def _fs_browser_core(label: str, key: str, mode: str = "file",
                     start: str | None = None, patterns: list[str] | None = None):
    """
    Render the core UI for the file system browser.

    Args:
        label (str): The label for the picker.
        key (str): Unique key for session state.
        mode (str): "file" or "dir".
        start (str | None): Initial path.
        patterns (list[str] | None): File patterns to match (e.g., ["*.txt"]).
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
    """
    Render a path picker widget (input field with a 'Browse' button).

    Args:
        label (str): Label for the input.
        key (str): Unique key for session state.
        mode (str): "file" or "dir".
        start (str | None): Initial directory path.
        patterns (list[str] | None): File glob patterns to filter (if mode="file").
        help (str | None): Tooltip text.

    Returns:
        str: The selected path.
    """
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


# ============================= Async Execution =============================

def _strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return ANSI_ESCAPE.sub("", s)


def _normalize_linebreaks(chunk: str) -> list[str]:
    """
    Clean and normalize log output chunks.

    Handles carriage returns, strip ANSI codes, and formats Nextflow-specific
    output patterns for better readability in the log viewer.

    Args:
        chunk (str): Raw output chunk.

    Returns:
        list[str]: list of cleaned log lines.
    """
    if not chunk:
        return []
    chunk = _strip_ansi(chunk).replace("\r", "\n")
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    parts = [p.rstrip() for p in chunk.split("\n") if p.strip() != ""]
    return parts

async def _async_read_stream(stream, log_q: Queue, stop_event: threading.Event):
    """
    Async coroutine to read from a stream and put lines into a queue.

    Args:
        stream: The asyncio stream to read from (stdout/stderr).
        log_q (Queue): The queue to put lines into.
        stop_event (threading.Event): Event to signal stopping.
    """
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
    """
    Async coroutine to execute a subprocess and stream its output.

    Args:
        full_cmd (str): The shell command to execute.
        log_q (Queue): Queue for logs.
        status_q (Queue): Queue for status messages/return code.
        stop_event (threading.Event): Event to trigger termination.
    """
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
    """Entry point for the background thread running the async loop."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_exec(full_cmd, log_q, status_q, stop_event))
    finally:
        loop.close()

def start_async_runner_ns(full_cmd: str, ns: str):
    """
    Start a background thread to run a command asynchronously.

    Initializes queues and events in session_state[ns_...] and starts the thread.

    Args:
        full_cmd (str): The command to run.
        ns (str): Namespace string to prefix session state keys.
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
    """Signal the background runner to stop."""
    ev = st.session_state.get(f"{ns}_stop_event")
    if ev and not ev.is_set():
        ev.set()


def drain_log_queue_ns(ns: str, tail_limit: int = 200, max_pull: int = 500):
    """
    Drain logs from the queue into the session state list.

    Args:
        ns (str): Namespace string.
        tail_limit (int): Max number of lines to keep in history.
        max_pull (int): Max number of lines to pull per call.
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


def render_log_box_ns(ns: str, height: int = 560):
    """
    Render a scrollable log box component.

    Args:
        ns (str): Namespace string.
        height (int): Height of the box in pixels.
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


def check_status_and_finalize_ns(ns: str, status_box, report_zone=None):
    """
    Check the status queue for completion and update UI.

    Args:
        ns (str): Namespace string.
        status_box: Streamlit element for status messages.
        report_zone: Streamlit element for reports (unused but kept for API).

    Returns:
        bool: True if execution finished, False otherwise.
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
            status_box.error(msg or f"Run finished with code {rc}. See the log below.")
    return finalized

def run_cmd(cmd: str | List[str], cwd: str | None = None) -> tuple[int, str, str]:
    """
    Run a shell command synchronously.

    Args:
        cmd (str | List[str]): The command to run. Can be a string or list of strings.
        cwd (str | None): The working directory for execution.

    Returns:
        tuple[int, str, str]: A tuple containing (return_code, stdout, stderr).
    """
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


# ============================= Shared Bactopia Helpers =============================

ROOT_DIR = pathlib.Path(__file__).resolve().parent


def discover_samples_from_outdir(outdir: str) -> List[str]:
    """
    Discover samples in a Bactopia output directory.

    Args:
        outdir (str): Path to the Bactopia output directory.

    Returns:
        List[str]: A list of detected sample names.
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
        if child.name.startswith("bactopia-") or child.name in {"bactopia-runs", "work", ".nextflow"}:
            continue
        candidates.append(child.name)
        # Classic Bactopia structure
        if (child / "main").exists() or (child / "tools").exists():
            samples_strict.append(child.name)

    if samples_strict:
        return samples_strict
    return candidates


def guess_bactopia_root_default(project_root: pathlib.Path | None = None) -> str:
    """
    Attempt to guess the Bactopia results folder location.

    Checks in order:
    1. st.session_state['outdir']
    2. BEAR_HUB_OUTDIR (env)
    3. BEAR_HUB_BASEDIR (env) or CWD + /bactopia_out
    4. Local project paths
    5. Fallback ~/BEAR_DATA/bactopia_out

    Args:
        project_root (pathlib.Path | None): Optional explicit project root to check.

    Returns:
        str: The best guess path.
    """
    candidates: list[pathlib.Path] = []

    # 1. Session State (from main BACTOPIA page)
    global_outdir = st.session_state.get("outdir")
    if global_outdir:
        base = pathlib.Path(global_outdir).expanduser()
        candidates.append(base)
        candidates.append(base / "bactopia_out")

    # 2. Environment Variable: BEAR_HUB_OUTDIR
    env_out = os.getenv("BEAR_HUB_OUTDIR")
    if env_out:
        candidates.append(pathlib.Path(env_out).expanduser().resolve())

    # 3. Environment Variable: BEAR_HUB_BASEDIR (or CWD)
    # This matches the default logic in BACTOPIA.py
    base_dir = os.getenv("BEAR_HUB_BASEDIR", os.getcwd())
    candidates.append((pathlib.Path(base_dir).expanduser() / "bactopia_out").resolve())

    # 4. Local Projects (using provided project_root or this file's parent)
    if project_root:
        candidates.append(project_root / "bactopia_out")

    # Also check relative to utils.py (ROOT_DIR)
    candidates.append(ROOT_DIR / "bactopia_out")

    # 5. Default fallback
    candidates.append(pathlib.Path.home() / "BEAR_DATA" / "bactopia_out")

    for cand in candidates:
        try:
            cand = cand.expanduser().resolve()
            if cand.exists() and cand.is_dir():
                if discover_samples_from_outdir(str(cand)):
                    return str(cand)
        except Exception:
            pass

    # If nothing worked, use the last fallback anyway
    return str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").expanduser().resolve())
