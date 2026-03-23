"""
System / environment utilities for BEAR-HUB.

Covers:
- Tool detection (which, docker, nextflow)
- Environment variable loading (.bear-hub.env)
- Directory management (state dir, NXF_HOME)
- Synchronous subprocess helper
- Session state initialization helper
"""

import os
import re
import pathlib
import shlex
import subprocess
from typing import List

import streamlit as st

from constants import APP_STATE_DIR, BEAR_HUB_CONFIG_DIR, BEAR_HUB_LEGACY_CONFIG


# ── Tool detection ────────────────────────────────────────────────────────────

def which(cmd: str) -> str | None:
    """Locate a command in the user's PATH."""
    from shutil import which as _which
    return _which(cmd)


def env_badge(label: str, ok: bool) -> str:
    """Return a simple status badge string."""
    return f"{'✅' if ok else '❌'} {label}"


def docker_available() -> bool:
    """Return True if 'docker' is found in PATH."""
    return which("docker") is not None


def get_nextflow_bin() -> str:
    """
    Return the Nextflow binary path.

    Resolution order:
    1. st.session_state['nextflow_bin']
    2. NEXTFLOW_BIN env var
    3. BACTOPIA_ENV_PREFIX/bin/nextflow
    4. 'nextflow' (rely on PATH)
    """
    v = (st.session_state.get("nextflow_bin") or "").strip()
    if v:
        return v
    v = (os.environ.get("NEXTFLOW_BIN") or "").strip()
    if v:
        return v
    bactopia_env = os.environ.get("BACTOPIA_ENV_PREFIX")
    if bactopia_env:
        try:
            cand = pathlib.Path(bactopia_env).expanduser().resolve() / "bin" / "nextflow"
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)
        except Exception:
            pass
    return "nextflow"


def nextflow_available() -> bool:
    """Return True if Nextflow is reachable."""
    nf_bin = get_nextflow_bin()
    if nf_bin != "nextflow":
        return True
    return which("nextflow") is not None


# ── Config loading ────────────────────────────────────────────────────────────

def bootstrap_bear_env_from_file() -> None:
    """
    Load environment variables from the BEAR-HUB config file.

    Search order (first match wins):
    1. ~/.bear-hub/config.env          (new path, written by refactored installer)
    2. $BEAR_HUB_ROOT/.bear-hub.env    (if BEAR_HUB_ROOT is set)
    3. ~/BEAR-HUB/.bear-hub.env        (legacy default from old install_bear.sh)

    Sets: BEAR_HUB_ROOT, BEAR_HUB_BASEDIR, BACTOPIA_ENV_PREFIX, NXF_CONDA_EXE.
    Skips if BACTOPIA_ENV_PREFIX is already set and NXF_CONDA_EXE is valid.
    """
    solver = os.environ.get("NXF_CONDA_EXE")
    if os.environ.get("BACTOPIA_ENV_PREFIX") and solver and os.path.exists(solver):
        return

    candidates: list[pathlib.Path] = []

    # 1. New recommended path
    candidates.append(BEAR_HUB_CONFIG_DIR / "config.env")

    # 2. BEAR_HUB_ROOT-relative path
    env_root = os.environ.get("BEAR_HUB_ROOT")
    if env_root:
        candidates.append(pathlib.Path(env_root).expanduser() / ".bear-hub.env")

    # 3. Legacy path
    candidates.append(BEAR_HUB_LEGACY_CONFIG)

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
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    if not var or not value:
                        continue
                    if var == "NXF_CONDA_EXE":
                        cur = os.environ.get("NXF_CONDA_EXE")
                        if not cur or not os.path.exists(cur):
                            os.environ["NXF_CONDA_EXE"] = value
                    else:
                        if var not in os.environ:
                            os.environ[var] = value
            break
        except Exception:
            continue

    if os.environ.get("BEAR_HUB_ROOT") and not os.environ.get("BEAR_HUB_BASEDIR"):
        os.environ["BEAR_HUB_BASEDIR"] = os.environ["BEAR_HUB_ROOT"]


# ── Directory management ──────────────────────────────────────────────────────

def ensure_state_dir() -> None:
    """Create the application state directory if it doesn't exist."""
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_nxf_home(default_outdir: str | None = None) -> str | None:
    """
    Ensure a writable NXF_HOME exists for Nextflow caching.

    Checks/creates in order:
    1. $NXF_HOME (if already set)
    2. $BEAR_HUB_OUTDIR/.nextflow or $BEAR_HUB_BASEDIR/.nextflow
    3. default_outdir/.nextflow
    4. ~/.nextflow
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
    Ensure a .nextflow directory exists in the given base path.

    Prevents 'No such file or directory' for .nextflow/history.lock.
    """
    try:
        base_path = pathlib.Path(base) if base is not None else pathlib.Path.cwd()
        proj_nxf = base_path / ".nextflow"
        proj_nxf.mkdir(parents=True, exist_ok=True)
        return str(proj_nxf)
    except Exception:
        return None


# ── Session state ─────────────────────────────────────────────────────────────

def init_session_state(defaults: dict) -> None:
    """
    Set session state keys to their default values if not already present.

    Call once at the top of each page to guard against KeyError on first load.

    Args:
        defaults: dict mapping key → default value
    """
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Subprocess ────────────────────────────────────────────────────────────────

def run_cmd(cmd: str | List[str], cwd: str | None = None) -> tuple[int, str, str]:
    """
    Run a command synchronously, returning (returncode, stdout, stderr).

    Args:
        cmd: Command as a string or list of strings.
        cwd: Working directory.
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
