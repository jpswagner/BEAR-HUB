#!/usr/bin/env bash
# stop_bear.sh — stop a running BEAR-HUB (frontend + backend), gracefully → forcefully.
# ---------------------------------------------------------------------------
# Why this exists:
#   `reflex run` launches a frontend (bun/node dev server) AND a backend
#   (granian) as children. Closing the browser tab stops nothing, and a plain
#   Ctrl+C in the wrong terminal can leave the frontend orphaned — which is how
#   a 34-day orphan + a 19 GB dev log happened once. This script finds the whole
#   process tree and takes it down cleanly (SIGINT → SIGTERM → SIGKILL).
#
# It is IDEMPOTENT: safe to run when nothing is up (exit 0). Used by run.sh
# (restart) and update_bear.sh (stop before update).
#
# Usage:
#   bash stop_bear.sh
# ---------------------------------------------------------------------------
set -uo pipefail   # NOT -e: stopping is best-effort; a dead PID must not abort us.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${HERE}/bearhub_rx"
PID_FILE="${HOME}/.bear-hub/bear-hub.pid"

log() { echo "[stop_bear] $*"; }

# Echo a PID plus every descendant (depth-first). Snapshotting the whole tree
# up front matters: once we SIGKILL the parent, its children are reparented to
# init and can no longer be found via the parent — so we must collect first.
collect_tree() {
    local pid="$1" child
    printf '%s\n' "${pid}"
    for child in $(pgrep -P "${pid}" 2>/dev/null); do
        collect_tree "${child}"
    done
}

# Does PID belong to *this* BEAR-HUB checkout? (its cwd or cmdline points here).
# Keeps the pattern-based fallback from ever touching an unrelated reflex/node.
belongs() {
    local pid="$1" cwd cmd
    cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
    cmd="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
    [[ "${cwd}" == "${APP_DIR}"* ]] && return 0
    [[ "${cmd}" == *"${APP_DIR}"* ]] && return 0
    return 1
}

# Escalate INT → TERM → KILL over a fixed set of PIDs (children handled by being
# in the set). We kill the process SUBTREE, never a whole process group, so the
# shell that launched BEAR-HUB is never taken down with it.
stop_pidset() {
    local -a pids=("$@")
    [ "${#pids[@]}" -gt 0 ] || return 0
    local sig p
    for sig in INT TERM KILL; do
        local -a alive=()
        for p in "${pids[@]}"; do
            kill -0 "${p}" 2>/dev/null && alive+=("${p}")
        done
        [ "${#alive[@]}" -gt 0 ] || return 0
        log "signal ${sig} → ${alive[*]}"
        for p in "${alive[@]}"; do kill "-${sig}" "${p}" 2>/dev/null || true; done
        sleep 2
    done
}

# ── Collect target PIDs (dedup) ───────────────────────────────────────────────
declare -A seen=()
add_tree() {
    local root="$1" pid
    for pid in $(collect_tree "${root}" 2>/dev/null); do
        seen["${pid}"]=1
    done
}

# 1) PID file written by run.sh (launcher PID → its whole subtree = the app).
if [ -f "${PID_FILE}" ]; then
    file_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${file_pid}" ]] && kill -0 "${file_pid}" 2>/dev/null; then
        add_tree "${file_pid}"
    fi
    rm -f "${PID_FILE}"
fi

# 2) Fallback: scan for reflex/frontend/backend procs that belong to THIS checkout.
while read -r pid; do
    [ -n "${pid}" ] || continue
    if belongs "${pid}"; then add_tree "${pid}"; fi
done < <(pgrep -f "reflex run|${APP_DIR}/.web|bun --bun run dev|granian" 2>/dev/null | sort -u)

if [ "${#seen[@]}" -eq 0 ]; then
    log "no running BEAR-HUB instance found."
    exit 0
fi

stop_pidset "${!seen[@]}"

# Final report.
leftover=0
for pid in "${!seen[@]}"; do kill -0 "${pid}" 2>/dev/null && leftover=$((leftover+1)); done
if [ "${leftover}" -gt 0 ]; then
    log "WARNING: ${leftover} process(es) survived SIGKILL — inspect with: ps -o pid,stat,cmd -p ${!seen[*]}"
    exit 1
fi
log "BEAR-HUB stopped."
