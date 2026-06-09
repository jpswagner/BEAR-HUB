"""Environment bootstrap and tool detection for BEAR-HUB."""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

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


def get_default_outdir() -> str:
    env_out = os.getenv("BEAR_HUB_OUTDIR")
    if env_out:
        return str(pathlib.Path(env_out).expanduser().resolve())
    base = os.getenv("BEAR_HUB_BASEDIR")
    if base:
        return str((pathlib.Path(base).expanduser() / "bactopia_out").resolve())
    return str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").resolve())


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
