#!/usr/bin/env bash
# Run the RECOVERED Reflex app from committed bytecode.
#
# The Reflex .py source was lost (only .pyc bytecode survived). This script
# materialises each module's bytecode as a "sourceless" .pyc next to where its
# .py would live, then launches Reflex with the project env (Python 3.11).
#
# Bytecode source, in order of preference:
#   1) bearhub/**/__pycache__/*.cpython-311.pyc   (present on this dev box)
#   2) _recovered/bytecode/**/*.cpython-311.pyc   (committed on the `reflex` branch)
#      -> get it with: git checkout reflex -- bearhub_rx/_recovered/bytecode
#
# This is a stopgap until core/ is rebuilt as clean source (see docs/reflex/MIGRATION.md).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
PY=/home/cdctserver/BEAR-HUB/envs/bear-hub/bin    # Python 3.11 + reflex

placed=0
materialise() { # $1 = root dir containing __pycache__ trees
  while IFS= read -r pyc; do
    case "$1" in
      _recovered/bytecode) mod="${pyc#_recovered/bytecode/}";;
      *)                    mod="${pyc/\/__pycache__\//\/}";;
    esac
    mod="${mod/.cpython-311.pyc/.pyc}"
    mkdir -p "$(dirname "$mod")"; cp -f "$pyc" "$mod"; placed=$((placed+1))
  done < <(find "$1" -name '*.cpython-311.pyc' -not -path '*/.web/*' 2>/dev/null)
}
if find bearhub -name '*.cpython-311.pyc' -path '*/__pycache__/*' | grep -q .; then
  materialise bearhub
elif [ -d _recovered/bytecode ]; then
  materialise _recovered/bytecode
else
  echo "ERROR: no 3.11 bytecode found. Run: git checkout reflex -- bearhub_rx/_recovered/bytecode" >&2
  exit 1
fi
rm -f rxconfig.pyc   # Reflex requires the real rxconfig.py file on disk
echo "materialised $placed sourceless module(s); launching reflex (frontend :3200, backend :8200)…"
exec "$PY/reflex" run --env dev "$@"
