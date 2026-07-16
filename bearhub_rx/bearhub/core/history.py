"""Run history persistence for BEAR-HUB.

Each run is stored as a JSON record in APP_STATE_DIR/run_history.jsonl
(one JSON object per line, newest appended last).

Records survive app restarts and are loaded on the Runs page.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import uuid
from typing import Optional

from bearhub.core.system import APP_STATE_DIR

_HISTORY_FILE = APP_STATE_DIR / "run_history.jsonl"
_MAX_RECORDS  = 500   # cap to avoid unbounded growth


# ── Record schema ──────────────────────────────────────────────────────────────

def new_record(
    ns: str,
    page: str,
    cmd: str,
    outdir: str = "",
    n_samples: int = 0,
) -> dict:
    """Create a new run record (status='running')."""
    return {
        "id":        str(uuid.uuid4())[:8],
        "ns":        ns,
        "page":      page,
        "cmd":       cmd,
        "outdir":    outdir,
        "n_samples": n_samples,
        "status":    "running",
        "started":   time.time(),
        "finished":  None,
        "duration":  None,
        "exit_code": None,
        # OS process identity — persisted so a run can be stopped from any page
        # and reconciled after a backend restart (see set_proc_info /
        # reconcile_orphans). None until the process is actually spawned.
        "pid":       None,
        "pgid":      None,
    }


# ── Persistence ────────────────────────────────────────────────────────────────

def _path() -> pathlib.Path:
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return _HISTORY_FILE


def _write(records: list[dict]) -> None:
    """Atomically rewrite the history file (write-temp-then-rename).

    The rename is atomic on POSIX, so a concurrent reader never sees a
    half-written file. (For true multi-writer safety we'd move to SQLite; this
    keeps the JSONL format while removing the torn-write window.)
    """
    p = _path()
    tmp = p.with_suffix(p.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, p)


def append_record(record: dict) -> None:
    """Append or update a record. Uses `id` to update in-place if present."""
    records = load_all()
    existing = {r["id"]: i for i, r in enumerate(records)}
    if record["id"] in existing:
        records[existing[record["id"]]] = record
    else:
        records.append(record)
    # Trim to cap
    if len(records) > _MAX_RECORDS:
        records = records[-_MAX_RECORDS:]
    _write(records)


def load_all() -> list[dict]:
    """Load all records, newest last. Returns [] on missing/corrupt file."""
    p = _path()
    if not p.exists():
        return []
    records = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


def load_recent(n: int = 100) -> list[dict]:
    """Return the `n` most recent records, newest first."""
    return list(reversed(load_all()[-n:]))


def finish_record(run_id: str, exit_code: int) -> None:
    """Mark a running record as finished."""
    records = load_all()
    for r in records:
        if r["id"] == run_id and r["status"] == "running":
            r["status"]   = "success" if exit_code == 0 else "failed"
            r["exit_code"] = exit_code
            r["finished"]  = time.time()
            r["duration"]  = round(r["finished"] - r["started"])
            break
    _write(records)


def set_proc_info(run_id: str, pid: int, pgid: int) -> None:
    """Record the OS pid/pgid of a run's process so it can be stopped/reconciled."""
    records = load_all()
    for r in records:
        if r["id"] == run_id:
            r["pid"], r["pgid"] = pid, pgid
            break
    _write(records)


def _pid_alive(pid: Optional[int]) -> bool:
    """True if a PID currently exists (signal 0 probes without killing)."""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True   # exists but owned by another user
    except (ValueError, OSError):
        return False


def reconcile_orphans() -> list[tuple[str, Optional[int], Optional[int]]]:
    """Reconcile 'running' records against reality on startup.

    A record left 'running' after a restart is either:
      - genuinely dead  → its OS process is gone → mark 'interrupted';
      - a real orphan   → its process survived (reparented to init) → keep it
        'running' and return it so the UI can re-adopt and offer to stop it.

    Returns ``[(run_id, pid, pgid), ...]`` for the still-alive orphans.
    Supersedes cancel_stale(): liveness beats the old 24h heuristic and also
    cleans up legacy records that never recorded a pid.
    """
    records = load_all()
    changed = False
    alive: list[tuple[str, Optional[int], Optional[int]]] = []
    for r in records:
        if r.get("status") != "running":
            continue
        pid = r.get("pid")
        if _pid_alive(pid):
            alive.append((r["id"], pid, r.get("pgid")))
        else:
            r["status"]    = "interrupted"
            r["finished"]  = time.time()
            r["duration"]  = round(r["finished"] - r["started"]) if r.get("started") else None
            r["exit_code"] = -1
            changed = True
    if changed:
        _write(records)
    return alive


def cancel_stale() -> None:
    """Mark any 'running' records older than 24h as 'interrupted' on startup.

    Kept for backward compatibility; reconcile_orphans() is the preferred
    startup reconciler (it checks actual process liveness).
    """
    cutoff = time.time() - 86400
    records = load_all()
    changed = False
    for r in records:
        if r["status"] == "running" and r["started"] < cutoff:
            r["status"] = "interrupted"
            r["finished"] = r["started"]
            changed = True
    if changed:
        _write(records)


# ── Formatting helpers ─────────────────────────────────────────────────────────

def fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


def fmt_time(ts: Optional[float]) -> str:
    if ts is None:
        return "—"
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


STATUS_COLOR = {
    "running":     "blue",
    "success":     "green",
    "failed":      "red",
    "interrupted": "amber",
    "stopped":     "gray",
}
