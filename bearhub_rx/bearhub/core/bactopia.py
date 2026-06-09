"""Bactopia filesystem helpers: sample discovery, directory utilities."""
from __future__ import annotations

import os
import pathlib

from bearhub.core.system import get_default_outdir


def discover_samples(outdir: str | None = None) -> list[str]:
    """List sample folders in a Bactopia output directory."""
    if not outdir:
        outdir = ""
    p = pathlib.Path(outdir)
    if not p.is_dir():
        return []
    strict: list[str] = []
    loose: list[str] = []
    for child in sorted(p.iterdir(), key=lambda x: x.name):
        if not child.is_dir():
            continue
        if child.name.startswith("bactopia-") or child.name in {
            ".nextflow", "bactopia-runs", "work"
        }:
            continue
        loose.append(child.name)
        if (child / "main").exists() or (child / "tools").exists():
            strict.append(child.name)
    return strict if strict else loose


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
