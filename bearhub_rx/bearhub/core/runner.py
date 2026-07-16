"""Nextflow command builders and async process runner for BEAR-HUB."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shlex
import shutil
import signal
import subprocess
import time

from bearhub.core.system import (
    APP_STATE_DIR,
    get_bactopia_version,
    get_nextflow_bin,
)
from bearhub.core import history as _hist

MAX_LOG_LINES: int = 1500

# Live-log UI throttling: coalesce stdout into at most one state update every
# FLUSH_SECS (or once FLUSH_LINES have piled up), instead of one websocket push
# + full-list re-serialization per line. The on-disk log stays line-immediate.
FLUSH_LINES: int = 50
FLUSH_SECS: float = 0.3

# Per-namespace process registry (for stop()) and per-run_id registry (so any
# page — chiefly Runs — can monitor/stop any active run, enabling parallelism).
_PROCS: dict[str, asyncio.subprocess.Process] = {}
_PROCS_BY_ID: dict[str, asyncio.subprocess.Process] = {}
# run_id → pgid for runs adopted after a restart (their child handle is gone,
# but the process group survives and can still be signalled). See adopt().
_ORPHANS: dict[str, int] = {}

_LOG_DIR = APP_STATE_DIR / "logs"


def _group_alive(pgid: int) -> bool:
    """True if any process in the group `pgid` still exists."""
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def adopt(run_id: str, pgid: int) -> None:
    """Re-register an orphaned run (found alive by history.reconcile_orphans)
    so the Runs page can monitor and stop it after a backend restart."""
    if pgid:
        _ORPHANS[run_id] = pgid


def active_pgids() -> list[int]:
    """Process-group ids of every currently-live run (children + orphans).

    Used by system.shutdown() to tear down runs that now live in their own
    sessions (start_new_session=True), so the app's off-switch leaves nothing
    orphaned."""
    pgids: list[int] = []
    for p in _PROCS_BY_ID.values():
        if p.returncode is None:
            try:
                pgids.append(os.getpgid(p.pid))
            except ProcessLookupError:
                pass
    for pgid in _ORPHANS.values():
        if _group_alive(pgid):
            pgids.append(pgid)
    return list(dict.fromkeys(pgids))


def run_log_path(run_id: str) -> str:
    """Path to a run's on-disk live log (written line-by-line by stream())."""
    return str(_LOG_DIR / f"{run_id}.log")


def tail_run_log(run_id: str, n: int = MAX_LOG_LINES) -> list[str]:
    """Return the last `n` lines of a run's on-disk log (empty if none)."""
    p = _LOG_DIR / f"{run_id}.log"
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def active_run_ids() -> list[str]:
    """run_ids with a live process — direct children plus adopted orphans."""
    live = [rid for rid, p in _PROCS_BY_ID.items() if p.returncode is None]
    live += [rid for rid, pgid in _ORPHANS.items() if _group_alive(pgid)]
    return list(dict.fromkeys(live))


def is_active(run_id: str) -> bool:
    p = _PROCS_BY_ID.get(run_id)
    if p and p.returncode is None:
        return True
    pgid = _ORPHANS.get(run_id)
    return bool(pgid and _group_alive(pgid))

# ANSI escape sequence stripper
_ANSI = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]", re.IGNORECASE)

# Cursor-up escape (^[[<N>A) — rewind log lines for in-place progress bars
_CURSOR_UP = re.compile(r"\x1b\[(\d+)A")
_NF_CLEANUP = re.compile(r"(?<!^)\s+(?=executor\s*>)", re.IGNORECASE)


def _resolve_cursor_up(text: str) -> list[str]:
    """Expand ANSI cursor-up sequences so log lines replace earlier lines."""
    parts = re.split(r"(\x1b\[\d+A)", text)
    lines: list[str] = []
    for part in parts:
        m = _CURSOR_UP.fullmatch(part)
        if m:
            n = int(m.group(1))
            del lines[-n:]
        else:
            lines.extend(part.split("\n"))
    return lines


def normalize_chunk(chunk: bytes) -> list[str]:
    """Decode and clean a raw stdout chunk into display lines."""
    text = chunk.decode("utf-8", errors="replace")
    text = _ANSI.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [l for l in _resolve_cursor_up(text) if l.strip()]


def write_include_file(outdir: str, samples: list[str]) -> str:
    """Write an --include file (one sample per line) and return its path."""
    digest = hashlib.md5("\n".join(sorted(samples)).encode()).hexdigest()[:8]
    fname = str(APP_STATE_DIR / f"include_{digest}.txt")
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    import pathlib
    pathlib.Path(fname).write_text("\n".join(samples) + "\n", encoding="utf-8")
    return fname


def write_tool_params_file(outdir: str, wf: str, jp: dict) -> str:
    """Write a tool's float `-params-file` JSON; return its path ("" if empty)."""
    if not jp:
        return ""
    import json, pathlib
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    fname = str(APP_STATE_DIR / f"tool-params-{wf}.json")
    pathlib.Path(fname).write_text(json.dumps(jp, indent=2), encoding="utf-8")
    return fname


def nextflow_wf_cmd(
    wf: str,
    outdir: str,
    include_file: str,
    profile: str,
    threads: int,
    memory_gb: int = 0,
    resume: bool = True,
    tool_args: list[str] = (),
    global_extra: str = "",
    params_file: str = "",
) -> str:
    """
    Build a Nextflow command for a Bactopia Tool (`--wf` workflow).

    Bactopia 4.0 tools keep the `--bactopia <results> --include` model but must
    be launched via the tool's own main.nf (`-main-script`) — the top-level
    `--wf` entry doesn't declare `--bactopia`/`--include`, so Nextflow 26's
    strict validation rejects them there.
    """
    base: list[str] = [get_nextflow_bin(), "run", "bactopia/bactopia"]
    ver = get_bactopia_version()
    if ver:
        base += ["-r", f"v{ver}"]
    base += [
        "-main-script", f"workflows/bactopia-tools/{wf}/main.nf",
        "-profile", profile,
        "--bactopia", outdir,
    ]
    if include_file:
        base += ["--include", include_file]
    if params_file:
        base += ["-params-file", params_file]
    if threads > 0:
        base += ["--max_cpus", str(threads)]
    if memory_gb and memory_gb > 0:
        base += ["--max_memory", f"{memory_gb}.GB"]
    if resume:
        base += ["-resume"]
    base += list(tool_args)
    if global_extra.strip():
        base += shlex.split(global_extra)
    return " ".join(shlex.quote(x) for x in base)


def join_subcommands(labelled: list[tuple[str, str]]) -> str:
    """Join multiple tool commands with banners, optionally line-buffered."""
    stdbuf = shutil.which("stdbuf")
    parts: list[str] = []
    for banner, cmd in labelled:
        if stdbuf:
            cmd = f"{stdbuf} -oL -eL {cmd}"
        parts.append(f'echo "===== {banner} =====" ; {cmd}')
    return " ; ".join(parts)


async def stream(
    state, cmd: str, ns: str, *,
    work_dir: str = "",
    page: str = "",
    n_samples: int = 0,
) -> None:
    """
    Run cmd as a background shell process, stream stdout/stderr to state.log.

    Uses `async with state` to make state updates within the Reflex background
    event context. Replaces the per-namespace process in _PROCS so stop() can
    kill it. Persists a run record to history via core/history.py.
    """
    cwd = work_dir if work_dir and os.path.isdir(work_dir) else str(APP_STATE_DIR)
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Create history record before the process starts
    record = _hist.new_record(
        ns=ns, page=page or ns, cmd=cmd,
        outdir=work_dir, n_samples=n_samples,
    )
    _hist.append_record(record)
    run_id = record["id"]

    # Open the on-disk live log so any page (e.g. Runs) can tail this run.
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_fh = open(_LOG_DIR / f"{run_id}.log", "w", encoding="utf-8", buffering=1)

    async with state:
        state.running = True
        state.status = "running"
        state.log = []
        state.run_id = run_id

    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env={**os.environ, "PYTHONUNBUFFERED": "1", "NXF_ANSI_LOG": "false"},
        # Own session/group so stop() can take down the whole tree (bash →
        # nextflow → java → docker) with one killpg — signalling only the bash
        # shell (the old behaviour) left Nextflow and its containers orphaned.
        start_new_session=True,
    )
    _PROCS[ns] = proc
    _PROCS_BY_ID[run_id] = proc
    # Persist pid/pgid so the run survives a UI reload and can be reconciled
    # after a backend restart (history.reconcile_orphans → adopt).
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = proc.pid
    _hist.set_proc_info(run_id, proc.pid, pgid)

    def _persist(new_lines: list[str]) -> None:
        for ln in new_lines:
            log_fh.write(ln + "\n")

    # Coalesced UI updates: lines land on disk immediately (complete log) but are
    # pushed to Reflex state in batches, so a chatty Nextflow run doesn't trigger
    # one full-list re-serialization + websocket push per line (was O(n²)).
    pending: list[str] = []
    last_flush = time.monotonic()

    async def _flush(force: bool = False) -> None:
        nonlocal pending, last_flush
        if not pending:
            return
        if not force and len(pending) < FLUSH_LINES and \
                (time.monotonic() - last_flush) < FLUSH_SECS:
            return
        chunk, pending = pending, []
        last_flush = time.monotonic()
        async with state:
            state.log = (state.log + chunk)[-MAX_LOG_LINES:]

    try:
        buf = b""
        while True:
            try:
                chunk = await asyncio.wait_for(proc.stdout.read(4096),
                                               timeout=FLUSH_SECS)
            except asyncio.TimeoutError:
                # Process went quiet — push whatever is buffered so the UI never
                # sits on an un-flushed line while waiting for the next byte.
                await _flush(force=True)
                continue
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                lines = normalize_chunk(line_bytes + b"\n")
                if lines:
                    _persist(lines)
                    pending.extend(lines)
            await _flush()
        if buf:
            lines = normalize_chunk(buf)
            if lines:
                _persist(lines)
                pending.extend(lines)
        await _flush(force=True)
    except Exception as exc:
        await _flush(force=True)
        async with state:
            state.log = state.log + [f"[runner] error: {exc}"]

    rc = await proc.wait()
    _PROCS.pop(ns, None)
    _PROCS_BY_ID.pop(run_id, None)
    try:
        log_fh.close()
    except OSError:
        pass
    # Persist finish to history
    _hist.finish_record(run_id, rc)
    async with state:
        state.running = False
        state.status = "success" if rc == 0 else "failed"


async def _kill_pgid(pgid: int) -> None:
    """Escalate SIGINT → SIGTERM → SIGKILL over a process group until it's gone.

    SIGINT first mirrors Ctrl+C so Nextflow runs its own shutdown (stopping the
    Docker containers it launched); SIGKILL is the last-resort guarantee. Works
    for orphans too: a reparented process can't be wait()ed, so we poll the
    group's liveness instead of awaiting the child.
    """
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        if not _group_alive(pgid):
            return
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        for _ in range(16):          # up to ~8s per signal
            await asyncio.sleep(0.5)
            if not _group_alive(pgid):
                return


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    """Kill a live child run's whole process group (bash → nextflow → java → …)."""
    if proc.returncode is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    await _kill_pgid(pgid)
    try:                             # reap so it doesn't linger as a zombie
        await asyncio.wait_for(proc.wait(), timeout=2)
    except (asyncio.TimeoutError, ProcessLookupError):
        pass


async def stop(ns: str) -> None:
    """Terminate the running process for namespace `ns`."""
    proc = _PROCS.get(ns)
    if proc is None or proc.returncode is not None:
        return
    await _terminate(proc)
    _PROCS.pop(ns, None)
    # Mark any still-running record for this ns as stopped
    records = _hist.load_all()
    for r in reversed(records):
        if r["ns"] == ns and r["status"] == "running":
            _hist.finish_record(r["id"], -1)
            _PROCS_BY_ID.pop(r["id"], None)
            _ORPHANS.pop(r["id"], None)
            break


async def stop_run_id(run_id: str) -> None:
    """Terminate a specific run by id (used by the Runs monitor page).

    Handles both live children and orphans adopted after a restart — the latter
    have no child handle, so we signal their persisted process group directly.
    """
    proc = _PROCS_BY_ID.get(run_id)
    if proc is not None and proc.returncode is None:
        await _terminate(proc)
        _PROCS_BY_ID.pop(run_id, None)
        for ns, p in list(_PROCS.items()):
            if p is proc:
                _PROCS.pop(ns, None)
        _ORPHANS.pop(run_id, None)
        _hist.finish_record(run_id, -1)
        return
    # No live child: orphan (post-restart) — kill by persisted pgid.
    pgid = _ORPHANS.pop(run_id, None)
    if pgid is None:
        rec = next((r for r in _hist.load_all() if r["id"] == run_id), None)
        if rec:
            pgid = rec.get("pgid") or rec.get("pid")
    if pgid:
        await _kill_pgid(int(pgid))
    _hist.finish_record(run_id, -1)
