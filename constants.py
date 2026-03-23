"""
BEAR-HUB application-level constants.

Centralizes values that were previously duplicated across modules.
Import from here instead of defining inline.
"""

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

# ── Bactopia ──────────────────────────────────────────────────────────────────
# Default Bactopia conda env name created by install_bear.sh
BACTOPIA_ENV_NAME: str = "bactopia"

# Pinned Bactopia version used by install_bear.sh (can be overridden by env var)
BACTOPIA_VERSION_PINNED: str = "3.0.0"
