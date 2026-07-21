#!/usr/bin/env bash
# update_bear.sh — BEAR-HUB updater
# ---------------------------------------------------------------------------
# One safe command to bring an existing BEAR-HUB checkout up to date:
#   1. stash any local/untracked changes (restored at the end),
#   2. fast-forward pull the current branch from origin,
#   3. re-run install_bear.sh (idempotent — only adds what's missing),
#      keeping the Bactopia version already pinned in ~/.bear-hub/config.env,
#   4. clear the stale Reflex frontend so it rebuilds on next launch.
#
# Usage:
#   bash update_bear.sh
#
# Environment overrides:
#   BACTOPIA_VERSION   Force a specific Bactopia pin (otherwise: keep installed).
# ---------------------------------------------------------------------------
set -euo pipefail

# Resolve repo root from this script's own location (works from anywhere).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${HERE}"

CONFIG_FILE="${HOME}/.bear-hub/config.env"
STASH_TAG="update_bear.sh auto-stash $(date +%Y%m%d-%H%M%S)"
STASHED=0

echo "======================================="
echo "  BEAR-HUB Updater"
echo "======================================="
echo "Repo: ${HERE}"

# ── Sanity: must be a git checkout ────────────────────────────────────────────
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: ${HERE} is not a git checkout — cannot pull updates here."
    echo "Re-clone with: git clone https://github.com/jpswagner/BEAR-HUB.git"
    exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
OLD_REF="$(git rev-parse --short HEAD)"
echo "Branch: ${BRANCH} (at ${OLD_REF})"

# ── Step 0: stop any running instance ─────────────────────────────────────────
# A running app holds the ports and serves stale code; stopping it first avoids
# port clashes and half-updated states, and lets us safely clear .web later.
if [[ -x "${HERE}/stop_bear.sh" ]]; then
    echo
    echo "Stopping any running BEAR-HUB instance before updating..."
    bash "${HERE}/stop_bear.sh" || true
fi

# ── Step 1: guard local changes ───────────────────────────────────────────────
if [[ -n "$(git status --porcelain)" ]]; then
    echo
    echo "Local changes detected — stashing them (will restore afterwards)..."
    git stash push -u -m "${STASH_TAG}" >/dev/null
    STASHED=1
fi

restore_stash() {
    if [[ "${STASHED}" -eq 1 ]]; then
        echo
        echo "Restoring your stashed local changes..."
        if ! git stash pop >/dev/null 2>&1; then
            echo "WARNING: 'git stash pop' hit a conflict. Your changes are safe in:"
            echo "  git stash list   (look for: ${STASH_TAG})"
            echo "Resolve manually with 'git stash pop' / 'git checkout'."
        fi
    fi
}
trap restore_stash EXIT

# ── Step 2: fetch + fast-forward pull ─────────────────────────────────────────
echo
echo "Fetching latest from origin..."
git fetch origin "${BRANCH}"

if ! git pull --ff-only origin "${BRANCH}"; then
    echo
    echo "ERROR: cannot fast-forward — your branch has diverged from origin/${BRANCH}."
    echo "Inspect with 'git status' / 'git log --oneline origin/${BRANCH}'."
    echo "(No files were force-changed; your work is intact.)"
    exit 1
fi

NEW_REF="$(git rev-parse --short HEAD)"
if [[ "${OLD_REF}" == "${NEW_REF}" ]]; then
    echo "Already up to date (${NEW_REF})."
else
    echo "Updated: ${OLD_REF} → ${NEW_REF}"
fi

# ── Step 3: re-run installer, keeping the installed Bactopia pin ──────────────
# Honor an explicit override; otherwise reuse whatever the install recorded so
# an update never silently changes the pinned pipeline version.
if [[ -z "${BACTOPIA_VERSION:-}" && -f "${CONFIG_FILE}" ]]; then
    PINNED="$(. "${CONFIG_FILE}" >/dev/null 2>&1; echo "${BACTOPIA_VERSION:-}")"
    if [[ -n "${PINNED}" ]]; then
        export BACTOPIA_VERSION="${PINNED}"
        echo
        echo "Keeping installed Bactopia pin: ${BACTOPIA_VERSION}"
    fi
fi

echo
echo "Re-running installer (idempotent)..."
bash "${HERE}/install_bear.sh"

# ── Step 4: clear the stale Reflex frontend BUILD so it rebuilds ─────────────
# Do NOT delete the whole .web: it contains node_modules, and Reflex does not
# reinstall frontend dependencies on the next launch (`reflex init` only
# scaffolds the directory). Wiping it leaves .web without react-router, the
# production build dies with "react-router: command not found", and the app
# never comes back up after an update. Removing the compiled/built output is
# enough — Reflex recompiles the pages and rebuilds the frontend every launch.
WEB_DIR="${HERE}/bearhub_rx/.web"
if [[ -d "${WEB_DIR}" ]]; then
    echo
    echo "Clearing stale frontend build (keeping node_modules) — rebuilds on next launch..."
    rm -rf "${WEB_DIR}/build" "${WEB_DIR}/.states"
fi

echo
echo "======================================="
echo "  Update complete."
echo "======================================="
echo "Run BEAR-HUB with:"
echo "  bash \"${HERE}/bearhub_rx/run.sh\""
