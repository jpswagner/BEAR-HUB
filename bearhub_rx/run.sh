#!/usr/bin/env bash
# Run the BEAR-HUB Reflex app.
# Usage:  bash bearhub_rx/run.sh [reflex run args...]
# Default: dev mode (frontend :3200, backend :8200).
# The bear-hub conda environment must be installed (see install_bear.sh).
set -euo pipefail

# App dir = this script's dir; repo root = its parent (location-independent, so
# it works wherever BEAR-HUB was cloned and for any user).
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/.." && pwd)"
cd "${APP_DIR}"

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
    exec reflex run "$@"
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
exec "$PY" -m reflex run "$@"
