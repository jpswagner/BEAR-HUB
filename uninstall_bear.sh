#!/usr/bin/env bash
# uninstall_bear.sh — BEAR-HUB uninstaller
# ---------------------------------------------------------------------------
# Removes conda environments, config files, and (optionally) data/results
# created by install_bear.sh.
# ---------------------------------------------------------------------------
set -euo pipefail

APP_NAME="BEAR-HUB"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The project root is one level above the repo (~/BEAR-HUB)
BEAR_HUB_ROOT="$(dirname "${SCRIPT_DIR}")"
REPO_DIR="${SCRIPT_DIR}"

CONFIG_DIR="${HOME}/.bear-hub"
ENVS_DIR="${BEAR_HUB_ROOT}/envs"
DATA_DIR="${BEAR_HUB_ROOT}/data"
OUT_DIR="${BEAR_HUB_ROOT}/bactopia_out"

echo "==========================================="
echo "   Uninstall ${APP_NAME}"
echo "==========================================="
echo
echo "This script will help you remove BEAR-HUB."
echo
echo "Detected paths:"
echo "  Repo        : ${REPO_DIR}"
echo "  Environments: ${ENVS_DIR}"
echo "  Data        : ${DATA_DIR}"
echo "  Output      : ${OUT_DIR}"
echo "  Config      : ${CONFIG_DIR}"
echo

read -rp "Are you sure you want to uninstall BEAR-HUB? [y/N] " confirm
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

removed_something=false

# ── Stop running Streamlit instances ─────────────────────────────────────────
echo
echo "--- Stopping running instances ---"
# Match the actual streamlit process for BEAR-HUB, excluding this script
if pgrep -f "streamlit run.*BEAR-HUB" >/dev/null 2>&1; then
    echo "Found running BEAR-HUB Streamlit instance(s). Stopping..."
    pkill -f "streamlit run.*BEAR-HUB" || true
    sleep 2
    echo "Stopped."
else
    echo "No running instances found."
fi

# ── Remove conda environments ───────────────────────────────────────────────
echo
echo "--- Conda environments (${ENVS_DIR}) ---"
if [[ -d "${ENVS_DIR}" ]]; then
    echo "Size: $(du -sh "${ENVS_DIR}" 2>/dev/null | cut -f1)"
    read -rp "Remove conda environments? [y/N] " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        rm -rf "${ENVS_DIR}"
        echo "Removed."
        removed_something=true
    else
        echo "Skipped."
    fi
else
    echo "Not found — skipping."
fi

# ── Remove config directory (~/.bear-hub/) ───────────────────────────────────
echo
echo "--- Config directory (${CONFIG_DIR}) ---"
if [[ -d "${CONFIG_DIR}" ]]; then
    read -rp "Remove config directory? [y/N] " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        rm -rf "${CONFIG_DIR}"
        echo "Removed."
        removed_something=true
    else
        echo "Skipped."
    fi
else
    echo "Not found — skipping."
fi

# ── Remove legacy config inside repo ─────────────────────────────────────────
if [[ -f "${BEAR_HUB_ROOT}/.bear-hub.env" ]]; then
    echo
    echo "--- Legacy config (${BEAR_HUB_ROOT}/.bear-hub.env) ---"
    read -rp "Remove legacy config file? [y/N] " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        rm -f "${BEAR_HUB_ROOT}/.bear-hub.env"
        echo "Removed."
        removed_something=true
    fi
fi

# ── Remove data and output directories ───────────────────────────────────────
echo
echo "--- Data & output directories ---"
has_data=false
if [[ -d "${DATA_DIR}" ]]; then
    echo "  Data   : ${DATA_DIR} ($(du -sh "${DATA_DIR}" 2>/dev/null | cut -f1))"
    has_data=true
fi
if [[ -d "${OUT_DIR}" ]]; then
    echo "  Output : ${OUT_DIR} ($(du -sh "${OUT_DIR}" 2>/dev/null | cut -f1))"
    has_data=true
fi

if ${has_data}; then
    echo
    echo "WARNING: These may contain your analysis results!"
    read -rp "Remove data and output directories? [y/N] " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        [[ -d "${DATA_DIR}" ]] && rm -rf "${DATA_DIR}" && echo "  Removed: ${DATA_DIR}"
        [[ -d "${OUT_DIR}" ]]  && rm -rf "${OUT_DIR}"  && echo "  Removed: ${OUT_DIR}"
        removed_something=true
    else
        echo "Skipped — your data is preserved."
    fi
else
    echo "Not found — skipping."
fi

# ── Remove repository directory ──────────────────────────────────────────────
echo
echo "--- Repository (${REPO_DIR}) ---"
if [[ -d "${REPO_DIR}" ]]; then
    read -rp "Remove the BEAR-HUB repository? [y/N] " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        rm -rf "${REPO_DIR}"
        echo "Removed."
        removed_something=true
    else
        echo "Skipped."
    fi
else
    echo "Not found — skipping."
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo
echo "==========================================="
if ${removed_something}; then
    echo "   Uninstallation complete."
else
    echo "   Nothing was removed."
fi
echo "==========================================="
echo
