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
# Default is PRODUCTION single-port on ${BEAR_HUB_PORT:-3200}. Extra flags
# (e.g. `--loglevel debug`) are APPENDED to the prod defaults so they don't
# silently drop the app into dev mode — a real trap: `run.sh --loglevel debug`
# used to become a bare `reflex run` (= dev). To pick the mode yourself, pass
# `--env` explicitly (e.g. `run.sh --env dev`) and your args are used verbatim.
PORT="${BEAR_HUB_PORT:-3200}"
PROD_ARGS=(--env prod --single-port --frontend-port "${PORT}" --backend-port "${PORT}")
if [ "$#" -eq 0 ]; then
  RUN_ARGS=("${PROD_ARGS[@]}")
elif printf '%s\n' "$@" | grep -qE -- '^--env(=|$)'; then
  # Caller chose the mode explicitly — respect their args verbatim.
  RUN_ARGS=("$@")
else
  # Extra flags but no mode → keep prod defaults and append them.
  RUN_ARGS=("${PROD_ARGS[@]}" "$@")
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

# ── Put the env's bin first on PATH ───────────────────────────────────────────
# Reflex's production build compresses the exported frontend by running
# `node compress-static.js`, locating node via `which node` — the FIRST node on
# PATH. An EOL system node (e.g. 12.22.x) can't run it and the build dies with
# "Failed to compress the exported frontend". The installer ships a modern node
# inside the env; prepend its bin so `which node` resolves there, not to an old
# system node. (Bactopia is launched by explicit prefix, so this doesn't affect it.)
ENV_BIN="$(cd "$(dirname "$PY")" && pwd)"
export PATH="${ENV_BIN}:${PATH}"

# ── Self-heal: make sure the frontend dependencies are present ────────────────
# `reflex run` compiles the frontend but never installs node_modules, and
# `reflex init` only scaffolds .web. If node_modules is missing (a wiped .web, an
# interrupted install), the production build dies with
# "react-router: command not found" and the app never comes up. Install them here
# so a launch always recovers on its own.
if [ ! -x ".web/node_modules/.bin/react-router" ]; then
  echo "Frontend dependencies missing — installing (one-time, ~1 min)..."
  [ -f ".web/package.json" ] || "$PY" -m reflex init
  BUN=""
  for cand in \
      "${HOME}/.local/share/reflex/bun/bin/bun" \
      "${HOME}/.bun/bin/bun"; do
    if [ -x "$cand" ]; then BUN="$cand"; break; fi
  done
  [ -n "$BUN" ] || BUN="$(command -v bun || true)"
  if [ -n "$BUN" ]; then
    ( cd .web && "$BUN" install ) || true
  fi
  if [ ! -x ".web/node_modules/.bin/react-router" ]; then
    echo "WARNING: could not install the frontend dependencies automatically." >&2
    echo "  Try:  cd \"${APP_DIR}/.web\" && bun install" >&2
  fi
fi

echo "BEAR-HUB Reflex — launching with: ${PY} -m reflex"
exec "$PY" -m reflex run "${RUN_ARGS[@]}"
