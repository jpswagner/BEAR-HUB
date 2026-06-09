"""Run history persistence for BEAR-HUB.

Each run is stored as a JSON record in APP_STATE_DIR/run_history.jsonl
(one JSON object per line, newest appended last).

Records survive app restarts and are loaded on the Runs page.
"""
from __future__ import annotations

import json
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
    }


# ── Persistence ────────────────────────────────────────────────────────────────

def _path() -> pathlib.Path:
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return _HISTORY_FILE


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
    _path().write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


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
    _path().write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def cancel_stale() -> None:
    """Mark any 'running' records older than 24h as 'interrupted' on startup."""
    cutoff = time.time() - 86400
    records = load_all()
    changed = False
    for r in records:
        if r["status"] == "running" and r["started"] < cutoff:
            r["status"] = "interrupted"
            r["finished"] = r["started"]
            changed = True
    if changed:
        _path().write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )


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
