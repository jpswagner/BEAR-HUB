#!/usr/bin/env bash
# Run the BEAR-HUB Reflex app.
# Usage:  bash bearhub_rx/run.sh [reflex run args...]
#
# Default: PRODUCTION single-port mode on :3200 (set BEAR_HUB_PORT to change).
# Why not dev mode? The Reflex dev frontend (`react-router dev`) crashes with the
# current toolchain (react-router 7 / vite 8): "jsxDEV is not a function" /
# "Cannot access 'abort' before initialization". The production build is
# unaffected, so we serve it. --single-port keeps frontend + backend on one port
# (which prod requires). Pass your own args to override (e.g. `--env dev` once the
# frontend toolchain is fixed / Node upgraded).
# The bear-hub conda environment must be installed (see install_bear.sh).
set -euo pipefail

# App dir = this script's dir; repo root = its parent (location-independent, so
# it works wherever BEAR-HUB was cloned and for any user).
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/.." && pwd)"
cd "${APP_DIR}"

# ── Lifecycle: stop any previous instance, then record this one ───────────────
# Prevents port clashes (3200/8200) and orphaned frontends — a stale dev server
# once grew a 19 GB log. stop_bear.sh is idempotent (no-op when nothing is up).
# $$ is preserved across the `exec` below, so the PID file points at the reflex
# launcher, whose process subtree is the frontend + backend.
CONFIG_DIR="${HOME}/.bear-hub"
mkdir -p "${CONFIG_DIR}"
if [ -x "${REPO_ROOT}/stop_bear.sh" ]; then
  echo "Checking for a previous BEAR-HUB instance..."
  "${REPO_ROOT}/stop_bear.sh" || true
fi
echo "$$" > "${CONFIG_DIR}/bear-hub.pid"

# ── Run arguments ─────────────────────────────────────────────────────────────
# No args → production single-port on ${BEAR_HUB_PORT:-3200}. Caller args win.
PORT="${BEAR_HUB_PORT:-3200}"
if [ "$#" -gt 0 ]; then
  RUN_ARGS=("$@")
else
  RUN_ARGS=(--env prod --single-port --frontend-port "${PORT}" --backend-port "${PORT}")
fi

# Resolve the bear-hub env's Python by path. We launch via `python -m reflex`
# (NOT the bin/reflex shim, whose shebang pip hardcodes to an absolute path and
# breaks if the env is moved) and avoid `conda run`, which isn't needed and may
# not even be on PATH at runtime.
PY=""
for cand in \
    "${BEAR_HUB_ROOT:-${REPO_ROOT}}/envs/bear-hub/bin/python" \
    "${REPO_ROOT}/envs/bear-hub/bin/python" \
    "${HOME}/BEAR-HUB/envs/bear-hub/bin/python" \
    "${HOME}/.conda/envs/bear-hub/bin/python"; do
  if [ -x "$cand" ]; then PY="$cand"; break; fi
done

# Last resort: a 'reflex' or 'python' already on PATH (e.g. an activated env).
if [ -z "$PY" ]; then
  if command -v reflex >/dev/null 2>&1; then
    echo "BEAR-HUB Reflex — launching with: reflex (PATH)"
    exec reflex run "${RUN_ARGS[@]}"
  fi
  PY="$(command -v python3 || command -v python || true)"
fi

if [ -z "$PY" ] || ! "$PY" -c "import reflex" >/dev/null 2>&1; then
  echo "ERROR: could not find the 'bear-hub' environment with Reflex installed." >&2
  echo "  Looked under: ${REPO_ROOT}/envs/bear-hub" >&2
  echo "  Run the installer first:  bash \"${REPO_ROOT}/install_bear.sh\"" >&2
  exit 1
fi

echo "BEAR-HUB Reflex — launching with: ${PY} -m reflex"
exec "$PY" -m reflex run "${RUN_ARGS[@]}"
