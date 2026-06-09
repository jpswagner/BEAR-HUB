"""Nextflow command builders and async process runner for BEAR-HUB."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shlex
import shutil
import subprocess

from bearhub.core.system import (
    APP_STATE_DIR,
    get_bactopia_version,
    get_nextflow_bin,
)
from bearhub.core import history as _hist

MAX_LOG_LINES: int = 1500

# Per-namespace process registry (for stop())
_PROCS: dict[str, asyncio.subprocess.Process] = {}

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

    async with state:
        state.running = True
        state.status = "running"
        state.log = []

    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env={**os.environ, "PYTHONUNBUFFERED": "1", "NXF_ANSI_LOG": "false"},
    )
    _PROCS[ns] = proc

    try:
        buf = b""
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            # flush on newline
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                lines = normalize_chunk(line_bytes + b"\n")
                if lines:
                    async with state:
                        state.log = (state.log + lines)[-MAX_LOG_LINES:]
        if buf:
            lines = normalize_chunk(buf)
            if lines:
                async with state:
                    state.log = (state.log + lines)[-MAX_LOG_LINES:]
    except Exception as exc:
        async with state:
            state.log = state.log + [f"[runner] error: {exc}"]

    rc = await proc.wait()
    _PROCS.pop(ns, None)
    # Persist finish to history
    _hist.finish_record(run_id, rc)
    async with state:
        state.running = False
        state.status = "success" if rc == 0 else "failed"


async def stop(ns: str) -> None:
    """Terminate the running process for namespace `ns`."""
    proc = _PROCS.get(ns)
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    _PROCS.pop(ns, None)
    # Mark any still-running record for this ns as stopped
    records = _hist.load_all()
    for r in reversed(records):
        if r["ns"] == ns and r["status"] == "running":
            _hist.finish_record(r["id"], -1)
            break
