#!/usr/bin/env bash
# Run the BEAR-HUB Reflex app.
# Usage:  bash bearhub_rx/run.sh [--env prod]
# Default: dev mode (frontend :3200, backend :8200).
# The bear-hub conda environment must be installed (see install_bear.sh).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"

# Locate Python from the bear-hub env (path set by install_bear.sh / bootstrap_env)
if [ -n "${BACTOPIA_ENV_PREFIX:-}" ]; then
  PY="${BACTOPIA_ENV_PREFIX}/../bear-hub/bin/python"
else
  PY="$(conda run -n bear-hub which python 2>/dev/null || true)"
fi
# Fall back: search common locations
for candidate in \
    "${HOME}/BEAR-HUB/envs/bear-hub/bin/reflex" \
    "${HOME}/.conda/envs/bear-hub/bin/reflex" \
    "$(which reflex 2>/dev/null || true)"; do
  [ -x "$candidate" ] && { REFLEX="$candidate"; break; }
done
REFLEX="${REFLEX:-reflex}"

echo "BEAR-HUB Reflex — launching with: $REFLEX"
exec "$REFLEX" run "$@"
