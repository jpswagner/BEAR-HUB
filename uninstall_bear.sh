#!/usr/bin/env bash
# uninstall_bear.sh — BEAR-HUB uninstaller
# ---------------------------------------------------------------------------
# Removes the conda environments, config/state files and (optionally) the data
# and results created by install_bear.sh.
#
# Paths come from ~/.bear-hub/config.env — the file the installer writes and the
# only authoritative record of where things went (BEAR_HUB_OUTDIR may well point
# at another disk). Without it we fall back to the repo layout. An earlier
# version derived them from the repo's *parent*, which for a standard clone at
# ~/BEAR-HUB resolved to $HOME: it offered to delete ~/data and ~/bactopia_out
# while leaving the multi-GB envs behind.
#
# Usage:
#   bash uninstall_bear.sh              # interactive, prompts per category
#   bash uninstall_bear.sh --dry-run    # show exactly what would be removed
# ---------------------------------------------------------------------------
set -euo pipefail

APP_NAME="BEAR-HUB"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]] && DRY_RUN=1

# Refuse to run destructively without a terminal. `yes | bash uninstall_bear.sh`
# would otherwise answer every prompt for you — the precise accident that cost a
# live install here. --dry-run stays scriptable, since it removes nothing.
if [[ "${DRY_RUN}" -eq 0 && ! -t 0 ]]; then
    echo "ERROR: refusing to uninstall non-interactively (stdin is not a terminal)."
    echo "Run it from a terminal, or preview with: bash uninstall_bear.sh --dry-run"
    exit 1
fi

CONFIG_DIR="${HOME}/.bear-hub"
CONFIG_FILE="${CONFIG_DIR}/config.env"
STATE_DIR="${HOME}/.bactopia_ui_local"     # update.log, run bookkeeping
LEGACY_CONFIG="${HOME}/.bear-hub.env"

# ── Resolve what to remove ────────────────────────────────────────────────────
# Read the installer's own record first; fall back to the repo layout. Note the
# fallback is REPO_DIR itself, not its parent — the installer sets
# BEAR_HUB_ROOT to the repo directory.
if [[ -f "${CONFIG_FILE}" ]]; then
    # shellcheck disable=SC1090
    . "${CONFIG_FILE}" >/dev/null 2>&1 || true
    CONFIG_SOURCE="${CONFIG_FILE}"
else
    CONFIG_SOURCE="(not found — using the repo layout)"
fi

ROOT="${BEAR_HUB_ROOT:-${REPO_DIR}}"
ENVS_DIR="${ROOT}/envs"
[[ -n "${BACTOPIA_ENV_PREFIX:-}" ]] && ENVS_DIR="$(dirname "${BACTOPIA_ENV_PREFIX}")"
DATA_DIR="${BEAR_HUB_BASEDIR:-${ROOT}/data}"
OUT_DIR="${BEAR_HUB_OUTDIR:-${ROOT}/bactopia_out}"

# ── Safety ────────────────────────────────────────────────────────────────────
# Refuse anything that would take out a home or system directory. A wrong path
# here is unrecoverable, so this check gates every single removal below.
is_safe_target() {
    local p="${1:-}" real
    [[ -n "${p}" ]] || return 1
    real="$(cd "${p}" 2>/dev/null && pwd -P)" || return 1
    case "${real}" in
        /|/home|/home/*/|/root|/usr|/usr/*|/etc|/var|/opt|/tmp|/mnt|/media) return 1 ;;
    esac
    [[ "${real}" != "${HOME}" ]] || return 1
    [[ "$(dirname "${real}")" != "/" ]] || return 1
    return 0
}

size_of() { du -sh "$1" 2>/dev/null | cut -f1; }

# remove <label> <path> [warning]
# Prints what it is, asks, then removes. Skips anything the safety check rejects.
remove_item() {
    local label="$1" path="$2" warn="${3:-}" confirm
    echo
    echo "--- ${label} ---"
    if [[ ! -e "${path}" ]]; then
        echo "  ${path}"
        echo "  Not found — skipping."
        return 0
    fi
    echo "  ${path}  ($(size_of "${path}"))"
    if ! is_safe_target "${path}"; then
        echo "  REFUSING: this resolves to a home or system directory."
        echo "  Remove it by hand if that is really what you want."
        return 0
    fi
    [[ -n "${warn}" ]] && echo "  WARNING: ${warn}"
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        echo "  [dry-run] would remove."
        return 0
    fi
    read -rp "  Remove? [y/N] " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        rm -rf "${path}"
        echo "  Removed."
        removed_something=true
    else
        echo "  Skipped."
    fi
}

# ── Plan ──────────────────────────────────────────────────────────────────────
echo "==========================================="
echo "   Uninstall ${APP_NAME}"
[[ "${DRY_RUN}" -eq 1 ]] && echo "   (dry run — nothing will be removed)"
echo "==========================================="
echo
echo "Paths read from: ${CONFIG_SOURCE}"
echo
echo "Repo         : ${REPO_DIR}"
echo "Environments : ${ENVS_DIR}"
echo "Data         : ${DATA_DIR}"
echo "Output       : ${OUT_DIR}"
echo "Config       : ${CONFIG_DIR}"
echo "App state    : ${STATE_DIR}"
echo
echo "Nextflow's own cache (~/.nextflow) is left alone — it is shared with any"
echo "other Nextflow use on this machine. Remove it by hand if you want it gone."
echo

if [[ "${DRY_RUN}" -eq 0 ]]; then
    # Deliberately NOT a [y/N] prompt. A y/N gate is trivially satisfied by a
    # stray `yes |`, which is exactly how this script once wiped a live install
    # during testing. Requiring a typed word means an automated stream cannot
    # walk through the whole uninstall by accident.
    echo "Type 'uninstall' to proceed (anything else cancels)."
    read -rp "> " confirm
    if [[ "${confirm}" != "uninstall" ]]; then
        echo "Uninstall cancelled."
        exit 0
    fi
fi

removed_something=false

# ── Stop the running app ──────────────────────────────────────────────────────
echo
echo "--- Stopping any running instance ---"
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "  [dry-run] would run stop_bear.sh."
elif [[ -f "${REPO_DIR}/stop_bear.sh" ]]; then
    # stop_bear.sh targets this install's PID file. The old `pkill -f "reflex
    # run"` also killed unrelated Reflex apps — a real risk on a shared server.
    bash "${REPO_DIR}/stop_bear.sh" || true
else
    echo "  stop_bear.sh not found — stop the app manually if it is running."
fi

# ── Remove ────────────────────────────────────────────────────────────────────
remove_item "Conda environments" "${ENVS_DIR}"
remove_item "Config directory" "${CONFIG_DIR}"
remove_item "App state (update log, run bookkeeping)" "${STATE_DIR}"

if [[ -f "${LEGACY_CONFIG}" ]]; then
    remove_item "Legacy config file" "${LEGACY_CONFIG}"
fi

remove_item "Data directory" "${DATA_DIR}" "may contain your input samples!"
remove_item "Output directory" "${OUT_DIR}" "may contain your analysis results!"

# Last, so the script itself stays readable until the end.
remove_item "Repository" "${REPO_DIR}"

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "==========================================="
if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "   Dry run complete — nothing was removed."
elif ${removed_something}; then
    echo "   Uninstallation complete."
else
    echo "   Nothing was removed."
fi
echo "==========================================="
echo
