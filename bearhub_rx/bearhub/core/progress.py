"""Parse Nextflow/Bactopia log lines into a friendly progress + failure summary.

Pure functions (no Reflex/IO) so they're trivially unit-testable. Bactopia 4.0
(nf-bactopia plugin, NXF_ANSI_LOG=false) prints one line per process as
`[PROCESS hh/hhhhhh] STAGE:MODULE (tag)` and a final tally
`completed=N failed=M cached=K`. On failure Nextflow prints `ERROR ~ ...`,
`Error executing process > 'NAME (tag)'` and a `Work dir:` pointer.
"""
from __future__ import annotations

import re

_PROC = re.compile(r"\[PROCESS [0-9a-f]+/[0-9a-f]+\]\s+([A-Z0-9_]+):([A-Z0-9_]+)\s*(?:\(([^)]*)\))?")
_COUNTS = re.compile(r"completed=(\d+)\s+failed=(\d+)\s+cached=(\d+)")
_ERR_PROC = re.compile(r"Error executing process > '([^']+)'")
_ERR_MSG = re.compile(r"ERROR\s+~\s+(.*)")
_WORKDIR = re.compile(r"Work dir:\s*(\S+)?")


def parse(lines: list[str]) -> dict:
    """Summarise a run's log lines.

    Returns: current (str), stages (ordered distinct), n_proc (int),
    completed/failed/cached (int|None), error (dict|None).
    """
    stages: list[str] = []
    current = ""
    n_proc = 0
    completed = failed = cached = None
    err_proc = ""
    err_msg = ""
    workdir = ""

    for i, raw in enumerate(lines):
        ln = raw.strip()
        m = _PROC.search(ln)
        if m:
            stage, module, tag = m.group(1), m.group(2), (m.group(3) or "")
            n_proc += 1
            if stage not in stages:
                stages.append(stage)
            current = f"{module} ({tag})" if tag else module
            continue
        m = _COUNTS.search(ln)
        if m:
            completed, failed, cached = int(m.group(1)), int(m.group(2)), int(m.group(3))
            continue
        m = _ERR_PROC.search(ln)
        if m:
            err_proc = m.group(1)
            continue
        m = _ERR_MSG.search(ln)
        if m and not err_msg:
            err_msg = m.group(1).strip()
            continue
        m = _WORKDIR.match(ln)
        if m:
            # Nextflow sometimes puts the path on the same line, sometimes next.
            workdir = m.group(1) or ""
            if not workdir:
                for nxt in lines[i + 1:]:
                    if nxt.strip():
                        workdir = nxt.strip()
                        break

    error = None
    if err_proc or err_msg or (failed or 0) > 0:
        error = {"process": err_proc, "message": err_msg, "workdir": workdir}

    return {
        "current": current,
        "stages": stages,
        "n_proc": n_proc,
        "completed": completed,
        "failed": failed,
        "cached": cached,
        "error": error,
    }


def summary_line(p: dict) -> str:
    """One-line human summary, e.g. 'completed=11 failed=0 cached=0'."""
    if p.get("completed") is not None:
        return f"completed={p['completed']} failed={p['failed']} cached={p['cached']}"
    if p.get("current"):
        return f"running: {p['current']}"
    return ""
