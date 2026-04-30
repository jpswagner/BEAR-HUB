"""
SQLite-backed run history for BEAR-HUB.

Records pipeline executions so users can review past runs after browser
refreshes or app restarts. The database is stored in the application state
directory alongside presets and include files.
"""

import sqlite3
import datetime
import pathlib

from constants import APP_STATE_DIR

DB_PATH: pathlib.Path = APP_STATE_DIR / "run_history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT    NOT NULL,
    finished_at TEXT,
    page        TEXT    NOT NULL,
    samples     TEXT,
    command     TEXT,
    status      TEXT    NOT NULL DEFAULT 'running'
);
"""

# Rows stuck in 'running' beyond this many hours are assumed orphaned (the
# Streamlit session that started them was killed / reloaded).
_STALE_RUN_HOURS = 12


def _connect() -> sqlite3.Connection:
    """Open (and create if needed) the run history database."""
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_SQL)
    conn.commit()
    return conn


def record_run_start(page: str, samples: list[str], command: str) -> int:
    """
    Insert a new 'running' record and return its row ID.

    Args:
        page:    Page/module name (e.g. "BACTOPIA", "TOOLS", "MERLIN").
        samples: List of sample names being processed.
        command: The full shell command that was launched.

    Returns:
        The auto-generated run ID.
    """
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO runs (started_at, page, samples, command, status) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.datetime.now().isoformat(timespec="seconds"),
            page,
            ", ".join(samples) if samples else "",
            command,
            "running",
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def record_run_finish(run_id: int, success: bool) -> None:
    """
    Update an existing run record with its completion status.

    Args:
        run_id:  The ID returned by record_run_start.
        success: True for exit code 0, False otherwise.
    """
    status = "success" if success else "failed"
    conn = _connect()
    conn.execute(
        "UPDATE runs SET finished_at = ?, status = ? WHERE id = ?",
        (datetime.datetime.now().isoformat(timespec="seconds"), status, run_id),
    )
    conn.commit()
    conn.close()


def stale_cleanup(hours: int = _STALE_RUN_HOURS) -> int:
    """
    Mark abandoned 'running' rows as 'unknown'.

    A run that started more than *hours* ago but never recorded a finish is
    almost certainly orphaned (browser closed, Streamlit restarted, process
    killed). We don't know if it succeeded, so flag it as 'unknown' rather
    than leaving it stuck in 'running' forever.

    Returns:
        Number of rows updated.
    """
    cutoff = (
        datetime.datetime.now() - datetime.timedelta(hours=hours)
    ).isoformat(timespec="seconds")
    conn = _connect()
    cur = conn.execute(
        "UPDATE runs SET status = 'unknown' WHERE status = 'running' AND started_at < ?",
        (cutoff,),
    )
    conn.commit()
    updated = cur.rowcount or 0
    conn.close()
    return updated


def duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
    """
    Compute the elapsed time between two ISO timestamps.

    Returns None if either value is missing or unparseable.
    """
    if not started_at or not finished_at:
        return None
    try:
        s = datetime.datetime.fromisoformat(started_at)
        f = datetime.datetime.fromisoformat(finished_at)
        return max(0, int((f - s).total_seconds()))
    except (TypeError, ValueError):
        return None


def format_duration(seconds: int | None) -> str:
    """Render seconds as 'HH:MM:SS' or 'MM:SS' (or '—' when unknown)."""
    if seconds is None:
        return "—"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_runs(limit: int = 50) -> list[dict]:
    """
    Return the most recent run records, newest first.

    Each row additionally includes a 'duration_s' key with the elapsed
    seconds (or None if the run hasn't finished yet).
    """
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            d["duration_s"] = duration_seconds(d.get("started_at"), d.get("finished_at"))
            out.append(d)
        return out
    except Exception:
        return []
