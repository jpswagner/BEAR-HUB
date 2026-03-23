"""
Async subprocess execution utilities for BEAR-HUB.

Runs Nextflow/Bactopia commands in a background thread with an asyncio event
loop, streams stdout/stderr into a Queue, and exposes helpers to drain that
queue and display a scrollable log box in Streamlit.
"""

import os
import re
import html
import asyncio
import threading
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components

from utils.data import ANSI_ESCAPE


# ── Log processing ────────────────────────────────────────────────────────────

def _strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return ANSI_ESCAPE.sub("", s)


def _resolve_cursor_up(text: str) -> str:
    """
    Simulate ANSI cursor-up sequences to discard overwritten lines.

    Nextflow redraws its progress block by emitting ESC[nA (cursor up n lines)
    then overwriting those lines in-place. Without a real terminal both the old
    and new versions end up in the stream. This keeps only the final state.
    """
    parts = re.split(r"\x1b\[(\d+)A", text)
    lines: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            lines.extend(part.split("\n"))
        else:
            del lines[-int(part):]   # remove lines about to be overwritten
    return "\n".join(lines)


def _normalize_linebreaks(chunk: str) -> list[str]:
    """
    Clean and split a raw output chunk into displayable log lines.

    Handles carriage returns, ANSI codes, and Nextflow-specific output
    patterns (executor lines, process tick marks).
    """
    if not chunk:
        return []
    chunk = _resolve_cursor_up(chunk)
    chunk = _strip_ansi(chunk).replace("\r", "\n")
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    return [p.rstrip() for p in chunk.split("\n") if p.strip()]


# ── Async subprocess ──────────────────────────────────────────────────────────

async def _async_read_stream(stream, log_q: Queue, stop_event: threading.Event) -> None:
    """Read chunks from an asyncio stream and enqueue processed log lines."""
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            break
        for sub in _normalize_linebreaks(chunk.decode(errors="replace")):
            log_q.put(sub)
        if stop_event.is_set():
            break


async def _async_exec(
    full_cmd: str,
    log_q: Queue,
    status_q: Queue,
    stop_event: threading.Event,
) -> None:
    """
    Execute a shell command asynchronously, streaming output to queues.

    Args:
        full_cmd:   Shell command string (run via bash -c).
        log_q:      Queue for log lines.
        status_q:   Queue for completion status: ("rc", int) or ("error", str).
        stop_event: Set this to request early termination.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-c", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "COLUMNS": "250", "NXF_ANSI_LOG": "false"},
        )
    except Exception as e:
        status_q.put(("error", f"Failed to start process: {e}"))
        return

    t_out = asyncio.create_task(_async_read_stream(proc.stdout, log_q, stop_event))
    t_err = asyncio.create_task(_async_read_stream(proc.stderr, log_q, stop_event))

    while True:
        if stop_event.is_set():
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
            except ProcessLookupError:
                pass
            break
        if proc.returncode is not None:
            break
        await asyncio.sleep(0.1)

    try:
        await asyncio.gather(t_out, t_err)
    except Exception:
        pass

    rc = await proc.wait()
    status_q.put(("rc", rc))


def _thread_entry(
    full_cmd: str,
    log_q: Queue,
    status_q: Queue,
    stop_event: threading.Event,
) -> None:
    """Background thread entry point: runs the asyncio event loop."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_exec(full_cmd, log_q, status_q, stop_event))
    finally:
        loop.close()


# ── Public runner API ─────────────────────────────────────────────────────────

def start_async_runner_ns(full_cmd: str, ns: str) -> None:
    """
    Launch a background thread to run *full_cmd* and stream its output.

    All state is stored under session_state keys prefixed with *ns*.

    Args:
        full_cmd: The shell command to execute.
        ns:       Namespace prefix for session state keys.
    """
    log_q: Queue = Queue()
    status_q: Queue = Queue()
    stop_event = threading.Event()
    th = threading.Thread(
        target=_thread_entry,
        args=(full_cmd, log_q, status_q, stop_event),
        daemon=True,
    )
    th.start()
    st.session_state[f"{ns}_running"] = True
    st.session_state[f"{ns}_log_q"] = log_q
    st.session_state[f"{ns}_status_q"] = status_q
    st.session_state[f"{ns}_stop_event"] = stop_event
    st.session_state[f"{ns}_thread"] = th
    st.session_state[f"{ns}_live_log"] = []


def request_stop_ns(ns: str) -> None:
    """Signal the background runner identified by *ns* to stop."""
    ev = st.session_state.get(f"{ns}_stop_event")
    if ev and not ev.is_set():
        ev.set()


def drain_log_queue_ns(ns: str, tail_limit: int = 200, max_pull: int = 500) -> None:
    """
    Pull log lines from the queue into the session state buffer.

    Args:
        ns:         Namespace prefix.
        tail_limit: Maximum number of lines to keep in history.
        max_pull:   Maximum lines to pull per call (prevents blocking the UI).
    """
    q: Queue | None = st.session_state.get(f"{ns}_log_q")
    if not q:
        return
    buf: list[str] = st.session_state.get(f"{ns}_live_log", [])
    pulled = 0
    while pulled < max_pull:
        try:
            buf.append(q.get_nowait())
            pulled += 1
        except Empty:
            break
    if len(buf) > tail_limit:
        buf[:] = buf[-tail_limit:]
    st.session_state[f"{ns}_live_log"] = buf


# ── Nextflow progress parsing ─────────────────────────────────────────────────

_NXF_EVENT_RE = re.compile(
    r"\[[\w/\- ]+\]\s+(Submitted|Cached|Completed|Skipped|Failed)\s+process\s+>\s+(\S+)",
    re.IGNORECASE,
)
_NXF_ERROR_RE = re.compile(
    r"Process\s+[`']([^`']+)[`']\s+terminated with an error",
    re.IGNORECASE,
)


def parse_nxf_progress(lines: list[str]) -> dict[str, dict]:
    """
    Parse Nextflow log lines into a per-process status dict.

    Understands the plain-text format produced when NXF_ANSI_LOG=false.
    Returns {process_name: {submitted, completed, cached, failed}}.
    """
    status: dict[str, dict] = {}
    for line in lines:
        m = _NXF_EVENT_RE.search(line)
        if m:
            event, proc = m.group(1).lower(), m.group(2)
            entry = status.setdefault(proc, {"submitted": 0, "completed": 0, "cached": 0, "failed": 0})
            if event == "submitted":
                entry["submitted"] += 1
            elif event in ("completed", "skipped"):
                entry["completed"] += 1
            elif event == "cached":
                entry["cached"] += 1
            elif event == "failed":
                entry["failed"] += 1
        else:
            m2 = _NXF_ERROR_RE.search(line)
            if m2:
                proc = m2.group(1)
                status.setdefault(proc, {"submitted": 0, "completed": 0, "cached": 0, "failed": 0})
                status[proc]["failed"] += 1
    return status


def render_nxf_progress_ns(ns: str) -> None:
    """
    Render a compact live process-status table for a Nextflow run.

    Reads from the session state log buffer populated by drain_log_queue_ns.
    Shows nothing if no process events have been logged yet.
    """
    lines: list[str] = st.session_state.get(f"{ns}_live_log", [])
    progress = parse_nxf_progress(lines)
    if not progress:
        return

    rows = []
    for proc in sorted(progress):
        c = progress[proc]
        total = c["submitted"] + c["cached"]
        done = c["completed"] + c["cached"]
        if c["failed"]:
            icon = "✖"
        elif total > 0 and done == total:
            icon = "✔"
        else:
            icon = "⏳"
        rows.append({
            "": icon,
            "Process": proc,
            "Total": total,
            "Done": done,
            "Cached": c["cached"],
            "Failed": c["failed"],
        })

    import pandas as pd
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={
            "": st.column_config.TextColumn(width="small"),
            "Process": st.column_config.TextColumn(width="large"),
            "Total": st.column_config.NumberColumn(width="small"),
            "Done": st.column_config.NumberColumn(width="small"),
            "Cached": st.column_config.NumberColumn(width="small"),
            "Failed": st.column_config.NumberColumn(width="small"),
        },
    )


def render_log_box_ns(ns: str, height: int = 560) -> None:
    """
    Render a scrollable dark-background log box.

    Args:
        ns:     Namespace prefix.
        height: Height of the box in pixels.
    """
    lines: list[str] = st.session_state.get(f"{ns}_live_log", [])
    content = html.escape("\n".join(lines)) if lines else ""
    components.html(
        f"""
        <div id="logbox_{ns}" style="
            width:100%; height:{height - 40}px; margin:0 auto; padding:12px;
            overflow-y:auto; overflow-x:auto; background:#0b0b0b; color:#e6e6e6;
            border-radius:10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas,
                         'Liberation Mono', monospace;
            font-size:13px; line-height:1.35;">
          <pre style="margin:0; white-space:pre;">{content or "&nbsp;"}</pre>
        </div>
        <script>
          const el = document.getElementById("logbox_{ns}");
          if (el) {{ el.scrollTop = el.scrollHeight; }}
        </script>
        """,
        height=height,
        scrolling=False,
    )


def check_status_and_finalize_ns(ns: str, status_box, report_zone=None) -> bool:
    """
    Check the status queue and finalize the run if complete.

    Shows a success or error message in *status_box* and clears the running
    state so the UI can re-enable the Start button.

    Args:
        ns:          Namespace prefix.
        status_box:  Streamlit placeholder element for status messages.
        report_zone: Unused (kept for API compatibility).

    Returns:
        True if the run has finished, False if still running.
    """
    sq: Queue | None = st.session_state.get(f"{ns}_status_q")
    if not sq:
        return False

    finalized = False
    msg: str | None = None
    rc: int | None = None

    try:
        while True:
            kind, payload = sq.get_nowait()
            if kind == "error":
                msg = payload
                finalized = True
                rc = -1
            elif kind == "rc":
                rc = int(payload)
                finalized = True
    except Empty:
        pass

    if finalized:
        st.session_state[f"{ns}_running"] = False
        st.session_state[f"{ns}_thread"] = None
        st.session_state[f"{ns}_stop_event"] = None
        if rc == 0:
            status_box.success("Finished successfully.")
        else:
            status_box.error(msg or f"Run finished with exit code {rc}. Check the log below.")

    return finalized
