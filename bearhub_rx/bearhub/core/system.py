"""Environment bootstrap and tool detection for BEAR-HUB."""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys

APP_STATE_DIR: pathlib.Path = pathlib.Path.home() / ".bactopia_ui_local"
_CONFIG_DIR: pathlib.Path = APP_STATE_DIR
_LEGACY_CONFIG: pathlib.Path = pathlib.Path.home() / ".bear-hub.env"
_bactopia_version_cache: str | None = None


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def get_nextflow_bin() -> str:
    """Resolve the Nextflow binary (env var → bactopia env prefix → PATH)."""
    explicit = os.environ.get("NEXTFLOW_BIN", "").strip()
    if explicit:
        p = pathlib.Path(explicit).expanduser().resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    prefix = os.environ.get("BACTOPIA_ENV_PREFIX", "").strip()
    if prefix:
        cand = pathlib.Path(prefix).expanduser() / "bin" / "nextflow"
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return which("nextflow") or "nextflow"


def nextflow_available() -> bool:
    nf = get_nextflow_bin()
    return bool(which(nf) or (pathlib.Path(nf).is_file() and os.access(nf, os.X_OK)))


def get_bactopia_version() -> str | None:
    """
    Return the pinned Bactopia version (e.g. '4.0.0').

    Uses the installed bactopia CLI version when available so Nextflow pins
    the run to that tag with `-r` instead of pulling the GitHub default (which
    may need a newer Nextflow).

    The actual binary is authoritative — the BACTOPIA_VERSION env var only
    seeds the pinned install default and may differ from what's installed.
    """
    global _bactopia_version_cache
    if _bactopia_version_cache is not None:
        return _bactopia_version_cache
    nf = get_nextflow_bin()
    candidates: list[str] = []
    if nf and nf != "nextflow":
        candidates.append(str(pathlib.Path(nf).parent / "bactopia"))
    candidates.append("bactopia")
    for exe in candidates:
        try:
            r = subprocess.run(
                [exe, "--version"],
                capture_output=True, text=True, timeout=15,
            )
            m = re.search(r"bactopia\s+v?(\d+\.\d+\.\d+)", r.stdout + r.stderr,
                          re.IGNORECASE)
            if m:
                _bactopia_version_cache = m.group(1)
                return _bactopia_version_cache
        except OSError:
            pass
    _bactopia_version_cache = "4.0.0"
    return _bactopia_version_cache


def docker_available() -> bool:
    return bool(which("docker"))


def docker_running() -> bool:
    """True if the Docker daemon is reachable (not just the CLI installed).

    BEAR-HUB runs Bactopia with `-profile docker`, so a stopped daemon makes
    every run fail with a cryptic error. `docker info` is the cheap probe.
    """
    if not which("docker"):
        return False
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=8,
        )
        return r.returncode == 0
    except OSError:
        return False


def get_default_outdir() -> str:
    env_out = os.getenv("BEAR_HUB_OUTDIR")
    if env_out:
        return str(pathlib.Path(env_out).expanduser().resolve())
    base = os.getenv("BEAR_HUB_BASEDIR")
    if base:
        return str((pathlib.Path(base).expanduser() / "bactopia_out").resolve())
    return str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").resolve())


def shutdown() -> None:
    """Stop the whole BEAR-HUB app: frontend, backend and the `reflex run` parent.

    BEAR-HUB is launched (run.sh → `python -m reflex run`) as a single foreground
    process group holding the reflex launcher, the frontend (bun/node) and the
    granian backend worker — the same group the terminal signals on Ctrl+C.
    Closing the browser tab signals nothing, so the server keeps running; this is
    the explicit "off switch" the UI wires to a button.

    We can't just signal our own group and return: the very signal that stops the
    frontend also stops us mid-call. So we hand the job to a *detached* watchdog
    (`start_new_session=True` puts it in its own group, outside the one we kill)
    that escalates SIGINT → SIGTERM → SIGKILL over the group. SIGINT first mirrors
    Ctrl+C so reflex/granian/Nextflow shut down gracefully; the later steps are a
    guarantee that nothing — a stubborn dev server especially — is left orphaned.

    NOTE: any in-progress Nextflow/Bactopia run now lives in its OWN session
    (runner.stream uses start_new_session=True), so killing our group no longer
    reaches it. We therefore signal each run's process group explicitly first,
    so the off-switch still leaves nothing orphaned.
    """
    pg = os.getpgrp()
    # Gather live run process groups (best-effort — never let this block shutdown).
    run_pgids: list[int] = []
    try:
        from bearhub.core import runner as _runner  # late import: avoids cycle
        run_pgids = _runner.active_pgids()
    except Exception:
        run_pgids = []
    # The watchdog only uses os/time/signal syscalls, so a plain `python -c` in a
    # new session is enough and avoids fork-in-async-worker hazards. It stops the
    # runs first (graceful → forced), then our own group (frontend + backend).
    watchdog = (
        "import os,time,signal\n"
        f"run_pgids={run_pgids!r}\n"
        f"pg={pg}\n"
        "for rp in run_pgids:\n"
        "    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):\n"
        "        try: os.killpg(rp, s)\n"
        "        except OSError: break\n"
        "        time.sleep(1)\n"
        "for s in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):\n"
        "    try: os.killpg(pg, s)\n"
        "    except OSError: break\n"  # group already gone → nothing left to kill
        "    time.sleep(3)\n"
    )
    try:
        subprocess.Popen(
            [sys.executable, "-c", watchdog],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return
    except Exception:
        # Last resort: signal our own group directly (kills us too, which is fine).
        try:
            os.killpg(pg, signal.SIGINT)
        except OSError:
            os._exit(0)


def bootstrap_env() -> None:
    """Load env vars from the BEAR-HUB config file, if present."""
    candidates: list[pathlib.Path] = [
        _CONFIG_DIR / "config.env",
        _LEGACY_CONFIG,
    ]
    for cfg in candidates:
        p = pathlib.Path(cfg).expanduser()
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            if m:
                var, value = m.group(1), m.group(2).strip().strip('"').strip("'")
                os.environ.setdefault(var, value)
        if "BEAR_HUB_ROOT" not in os.environ:
            os.environ.setdefault("BEAR_HUB_ROOT", str(p.parent))
        break
