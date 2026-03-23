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


def get_runs(limit: int = 50) -> list[dict]:
    """
    Return the most recent run records, newest first.

    Args:
        limit: Maximum number of rows to return.

    Returns:
        List of dicts with keys: id, started_at, finished_at, page,
        samples, command, status.
    """
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
