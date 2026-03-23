"""
Bactopia-specific helper functions for BEAR-HUB.

Covers sample discovery and output-directory guessing.
"""

import os
import pathlib
from typing import List

import streamlit as st

# Root of the BEAR-HUB project (parent of utils/)
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent


def discover_samples_from_outdir(outdir: str) -> List[str]:
    """
    Discover sample names in a Bactopia output directory.

    Uses the classic Bactopia structure (subdirectory per sample, containing
    'main/' or 'tools/' subdirectories). Falls back to any non-administrative
    directory if none match the strict pattern.

    Args:
        outdir: Path to the Bactopia output directory.

    Returns:
        List of detected sample names, sorted alphabetically.
    """
    p = pathlib.Path(outdir)
    if not p.exists() or not p.is_dir():
        return []

    samples_strict: List[str] = []
    candidates: List[str] = []

    for child in sorted(p.iterdir(), key=lambda x: x.name):
        if not child.is_dir():
            continue
        if child.name.startswith("bactopia-") or child.name in {"bactopia-runs", "work", ".nextflow"}:
            continue
        candidates.append(child.name)
        if (child / "main").exists() or (child / "tools").exists():
            samples_strict.append(child.name)

    return samples_strict if samples_strict else candidates


def guess_bactopia_root_default(project_root: pathlib.Path | None = None) -> str:
    """
    Attempt to guess the Bactopia results folder location.

    Resolution order:
    1. st.session_state['outdir'] (set by the BACTOPIA page)
    2. $BEAR_HUB_OUTDIR env var
    3. $BEAR_HUB_BASEDIR/bactopia_out (or CWD/bactopia_out)
    4. project_root/bactopia_out (if provided)
    5. ROOT_DIR/bactopia_out
    6. ~/BEAR_DATA/bactopia_out (fallback)

    Returns the first path that exists and contains at least one sample;
    falls back to the last candidate regardless.

    Args:
        project_root: Optional explicit project root to check.
    """
    candidates: list[pathlib.Path] = []

    global_outdir = st.session_state.get("outdir")
    if global_outdir:
        base = pathlib.Path(global_outdir).expanduser()
        candidates.append(base)
        candidates.append(base / "bactopia_out")

    env_out = os.getenv("BEAR_HUB_OUTDIR")
    if env_out:
        candidates.append(pathlib.Path(env_out).expanduser().resolve())

    base_dir = os.getenv("BEAR_HUB_BASEDIR", os.getcwd())
    candidates.append((pathlib.Path(base_dir).expanduser() / "bactopia_out").resolve())

    if project_root:
        candidates.append(project_root / "bactopia_out")

    candidates.append(ROOT_DIR / "bactopia_out")
    candidates.append(pathlib.Path.home() / "BEAR_DATA" / "bactopia_out")

    for cand in candidates:
        try:
            cand = cand.expanduser().resolve()
            if cand.exists() and cand.is_dir() and discover_samples_from_outdir(str(cand)):
                return str(cand)
        except Exception:
            pass

    return str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").expanduser().resolve())
