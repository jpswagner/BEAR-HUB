"""In-app updater: pull the newest BEAR-HUB and re-verify the installation.

Why this runs detached
----------------------
`update_bear.sh` stops the app before updating (it has to: the running app holds
the port and would keep serving stale code). So the update cannot be run as a
normal child of the app — the app is killed halfway through and could never
report the result. Instead we spawn the updater in its OWN session
(``start_new_session=True``), so it survives the app going down. It writes
everything to ``APP_STATE_DIR/update.log`` and relaunches the app when finished;
the Status page then shows that log after the restart.

`stop_bear.sh` will not kill this updater: it only targets processes whose cwd or
cmdline points at ``bearhub_rx`` (the app dir), and the updater runs from the repo
root as ``bash update_bear.sh``.

What is NEVER touched (verified against the scripts)
----------------------------------------------------
- Run history, per-run logs and presets → ``APP_STATE_DIR`` (~/.bactopia_ui_local),
  outside the git repo entirely.
- Results (``bactopia_out/``, ``data/``, ``work/``, ``results/``) → gitignored, and
  ``git stash -u`` skips ignored files (only ``-a`` would take them).
- ``~/.bear-hub/config.env`` → rewritten by the installer, but update_bear.sh
  passes the already-pinned BACTOPIA_VERSION through so the pin never changes.

The only deletion in the whole flow is ``rm -rf bearhub_rx/.web`` — the frontend
build cache, regenerated on the next launch.
"""
from __future__ import annotations

import pathlib
import shlex
import subprocess

from bearhub.core.system import APP_STATE_DIR

# bearhub_rx/bearhub/core/updater.py -> repo root (same derivation as versions.py)
REPO_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parents[3]

_LOG = APP_STATE_DIR / "update.log"
_MARKER = APP_STATE_DIR / "update.running"


def _q(s: str) -> str:
    """Shell-quote a path for the generated updater script."""
    return shlex.quote(s)


def update_log_path() -> pathlib.Path:
    return _LOG


def _git(*args: str, timeout: int = 10) -> str:
    """Run a git command in the repo; '' on any failure."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def is_git_checkout() -> bool:
    return _git("rev-parse", "--is-inside-work-tree") == "true"


def git_info() -> dict[str, str]:
    """Branch / short ref / dirty flag for display on the Status page."""
    if not is_git_checkout():
        return {"is_git": "no", "branch": "", "ref": "", "dirty": "no"}
    return {
        "is_git": "yes",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "ref": _git("rev-parse", "--short", "HEAD"),
        "dirty": "yes" if _git("status", "--porcelain") else "no",
    }


def is_running() -> bool:
    """True while an update is in flight (marker written by the updater)."""
    return _MARKER.is_file()


def tail_log(n: int = 400) -> list[str]:
    """Last `n` lines of the most recent update log ([] if never updated)."""
    try:
        return _LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def start_update(relaunch: bool = True) -> bool:
    """Kick off the update in a detached session. Returns True if spawned.

    Sequence (all logged to update.log):
      1. update_bear.sh — stops the app, stashes local changes, ff-only pull,
         re-runs the idempotent installer (which re-verifies every dependency),
         clears the .web build cache, restores the stash.
      2. relaunch the app via run.sh, so the user gets it back automatically.
    """
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    script = REPO_ROOT / "update_bear.sh"
    if not script.is_file():
        _LOG.write_text(
            f"ERROR: {script} not found — is this a full BEAR-HUB checkout?\n",
            encoding="utf-8",
        )
        return False

    run_sh = REPO_ROOT / "bearhub_rx" / "run.sh"
    # Marker lets the UI say "an update is in flight" even across the restart.
    shell = f"""
set -u
: > {_q(str(_LOG))}
exec >> {_q(str(_LOG))} 2>&1
echo "=== BEAR-HUB update started: $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "repo: {_q(str(REPO_ROOT))}"
echo
touch {_q(str(_MARKER))}
bash {_q(str(script))}
rc=$?
echo
echo "=== update_bear.sh finished with exit code $rc ==="
rm -f {_q(str(_MARKER))}
if [ "$rc" -eq 0 ] && [ "{'1' if relaunch else '0'}" = "1" ]; then
    echo "=== relaunching BEAR-HUB ==="
    nohup bash {_q(str(run_sh))} >> {_q(str(_LOG))} 2>&1 &
    echo "relaunch started (pid $!)"
else
    echo "NOT relaunching (exit code $rc). Start manually: bash {run_sh}"
fi
echo "=== done: $(date '+%Y-%m-%d %H:%M:%S') ==="
"""
    try:
        subprocess.Popen(
            ["bash", "-c", shell],
            cwd=str(REPO_ROOT),
            start_new_session=True,          # survives the app being stopped
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return True
    except Exception as exc:                  # noqa: BLE001 - report, never crash the UI
        try:
            _LOG.write_text(f"ERROR: could not start updater: {exc}\n", encoding="utf-8")
        except OSError:
            pass
        return False
