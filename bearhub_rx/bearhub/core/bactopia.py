"""Bactopia filesystem helpers: sample discovery, directory utilities."""
from __future__ import annotations

import os
import pathlib

from bearhub.core.system import get_default_outdir


# Reserved Bactopia output folders that are never sample directories.
_RESERVED_DIRS = {".nextflow", "bactopia-runs", "work", "logs", "nf-reports"}


def _is_sample_dir(child: pathlib.Path) -> bool:
    """True only for genuine Bactopia per-sample output folders.

    A Bactopia 4.x sample directory contains a ``main/`` (core pipeline output)
    and/or ``tools/`` (Bactopia Tools output) subfolder. We require one of those
    markers so that pointing the picker at an arbitrary directory (e.g. ``$HOME``)
    never lists unrelated folders like ``.ssh`` or ``Downloads`` as "samples".
    """
    try:
        return (child / "main").is_dir() or (child / "tools").is_dir()
    except OSError:
        return False


def discover_samples(outdir: str | None = None) -> list[str]:
    """List genuine Bactopia sample folders in an output directory.

    Returns ``[]`` when the directory holds no real Bactopia samples — the UI
    treats an empty list as "no samples found" rather than offering arbitrary
    subdirectories for selection.
    """
    if not outdir:
        return []
    p = pathlib.Path(outdir)
    if not p.is_dir():
        return []
    samples: list[str] = []
    for child in sorted(p.iterdir(), key=lambda x: x.name):
        if not child.is_dir():
            continue
        # Skip dotfiles, bactopia-* bookkeeping dirs, and reserved folders.
        if child.name.startswith(".") or child.name.startswith("bactopia-"):
            continue
        if child.name in _RESERVED_DIRS:
            continue
        if _is_sample_dir(child):
            samples.append(child.name)
    return samples


def guess_root_default() -> str:
    """First existing Bactopia outdir with samples, else the default."""
    candidates: list[pathlib.Path] = []
    env_out = os.getenv("BEAR_HUB_OUTDIR")
    if env_out:
        candidates.append(pathlib.Path(env_out).expanduser())
    base = os.getenv("BEAR_HUB_BASEDIR", os.getcwd())
    candidates.append(pathlib.Path(base).expanduser() / "bactopia_out")
    candidates.append(pathlib.Path.home() / "BEAR_DATA" / "bactopia_out")
    for cand in candidates:
        try:
            cand = cand.expanduser().resolve()
            if cand.is_dir() and discover_samples(str(cand)):
                return str(cand)
        except OSError:
            pass
    return get_default_outdir()


def list_subdirs(path: str) -> list[str]:
    """Visible subdirectory names (for the directory picker)."""
    p = pathlib.Path(path).expanduser().resolve()
    try:
        return sorted(
            str(child.name)
            for child in p.iterdir()
            if child.is_dir() and not child.name.lower().startswith(".")
        )
    except (PermissionError, OSError):
        return []


def safe_dir(path: str | None) -> str:
    """Resolve to an existing directory, falling back to $HOME."""
    if not path:
        return str(pathlib.Path.home())
    try:
        p = pathlib.Path(path).expanduser().resolve()
        if p.is_dir():
            return str(p)
        # Walk up until we find an existing directory
        parent = p.parent
        while not parent.is_dir() and parent != parent.parent:
            parent = parent.parent
        if parent.is_dir():
            return str(parent)
    except OSError:
        pass
    return str(pathlib.Path.home())
