"""
BEAR-HUB utility package.

Re-exports every public symbol from the sub-modules so that existing code
that does ``import utils`` and calls ``utils.some_function()`` continues to
work without modification.

Sub-module layout
-----------------
utils/data.py       — static data (MLST schemes, genome sizes)
utils/system.py     — env/tool detection, config loading, directory helpers
utils/fs.py         — file-system browser widget
utils/exec.py       — async subprocess execution & log streaming
utils/bactopia.py   — Bactopia-specific helpers (sample discovery)
utils/validation.py — input path validation
utils/history.py    — SQLite run history
"""

# ── Data ──────────────────────────────────────────────────────────────────────
from utils.data import ANSI_ESCAPE, GENOME_SIZES, MLST_SCHEMES

# ── System ────────────────────────────────────────────────────────────────────
from utils.system import (
    which,
    env_badge,
    docker_available,
    get_nextflow_bin,
    nextflow_available,
    bootstrap_bear_env_from_file,
    ensure_state_dir,
    ensure_nxf_home,
    ensure_project_nxf_dir,
    init_session_state,
    run_cmd,
)

# ── File-system browser ───────────────────────────────────────────────────────
from utils.fs import (
    _safe_id,
    _list_dir,
    _st_rerun,
    _fs_browser_core,
    path_picker,
)

# ── Async execution ───────────────────────────────────────────────────────────
from utils.exec import (
    _strip_ansi,
    _normalize_linebreaks,
    parse_nxf_progress,
    render_nxf_progress_ns,
    start_async_runner_ns,
    request_stop_ns,
    drain_log_queue_ns,
    render_log_box_ns,
    check_status_and_finalize_ns,
)

# ── Bactopia helpers ──────────────────────────────────────────────────────────
from utils.bactopia import (
    ROOT_DIR,
    discover_samples_from_outdir,
    guess_bactopia_root_default,
)

# ── Validation ────────────────────────────────────────────────────────────────
from utils.validation import validate_path, validate_outdir

# ── Run history ───────────────────────────────────────────────────────────────
from utils.history import record_run_start, record_run_finish, get_runs

__all__ = [
    # data
    "ANSI_ESCAPE", "GENOME_SIZES", "MLST_SCHEMES",
    # system
    "which", "env_badge", "docker_available", "get_nextflow_bin",
    "nextflow_available", "bootstrap_bear_env_from_file",
    "ensure_state_dir", "ensure_nxf_home", "ensure_project_nxf_dir",
    "init_session_state", "run_cmd",
    # fs
    "_safe_id", "_list_dir", "_st_rerun", "_fs_browser_core", "path_picker",
    # exec
    "_strip_ansi", "_normalize_linebreaks",
    "parse_nxf_progress", "render_nxf_progress_ns",
    "start_async_runner_ns", "request_stop_ns",
    "drain_log_queue_ns", "render_log_box_ns", "check_status_and_finalize_ns",
    # bactopia
    "ROOT_DIR", "discover_samples_from_outdir", "guess_bactopia_root_default",
    # validation
    "validate_path", "validate_outdir",
    # history
    "record_run_start", "record_run_finish", "get_runs",
]
