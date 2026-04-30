"""
BEAR-HUB application-level constants.

Single source of truth for values that used to be duplicated across pages.
Import from here instead of redefining.
"""

import os
import pathlib

# ── GitHub ────────────────────────────────────────────────────────────────────
GITHUB_REPO = "jpswagner/BEAR-HUB"

# ── Local paths ───────────────────────────────────────────────────────────────
# Application state directory (presets, run history, include files…)
APP_STATE_DIR: pathlib.Path = pathlib.Path.home() / ".bactopia_ui_local"

# New recommended config location (written by install_bear.sh ≥ refactor)
BEAR_HUB_CONFIG_DIR: pathlib.Path = pathlib.Path.home() / ".bear-hub"

# Legacy config path (written by older install_bear.sh; kept for backward compat)
BEAR_HUB_LEGACY_CONFIG: pathlib.Path = pathlib.Path.home() / "BEAR-HUB" / ".bear-hub.env"


def get_default_outdir() -> str:
    """
    Resolve the default Bactopia-style output directory.

    Precedence:
      1. $BEAR_HUB_OUTDIR                     — explicit override.
      2. $BEAR_HUB_BASEDIR / "bactopia_out"   — paired with install base.
      3. ~/BEAR_DATA/bactopia_out             — fallback.

    Resolved at call time (not import time) so `run_bear.sh` can export
    these vars before Streamlit boots without pages needing to re-check.
    """
    env_out = os.getenv("BEAR_HUB_OUTDIR")
    if env_out:
        return str(pathlib.Path(env_out).expanduser().resolve())

    base = os.getenv("BEAR_HUB_BASEDIR")
    if base:
        return str((pathlib.Path(base).expanduser() / "bactopia_out").resolve())

    return str((pathlib.Path.home() / "BEAR_DATA" / "bactopia_out").resolve())


# ── Bactopia ──────────────────────────────────────────────────────────────────
# Default Bactopia conda env name created by install_bear.sh
BACTOPIA_ENV_NAME: str = "bactopia"

# Pinned Bactopia version used by install_bear.sh (can be overridden by env var)
BACTOPIA_VERSION_PINNED: str = "3.0.0"
