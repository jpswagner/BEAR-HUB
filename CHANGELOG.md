# Changelog

All notable changes to BEAR-HUB are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] — 2026-06-16

First stable release on the **Reflex** UI targeting **Bactopia 4.0** — hence the
major version bump from the 0.1.x Streamlit line.

### Added
- `update_bear.sh` — one safe command to update an existing checkout: stashes
  local/untracked changes, fast-forward pulls, re-runs the idempotent installer
  (keeping the Bactopia version already pinned in `~/.bear-hub/config.env`), and
  clears the stale Reflex `.web/` so the frontend rebuilds. `make update` now
  calls it.
- In-app **update-available** banner on the Status page. A best-effort,
  non-blocking GitHub check (`core/versions.py: check_for_update`) compares the
  local `VERSION` file against the latest release tag; offline labs see no error.
  The Status page also now shows the installed BEAR-HUB app version.
- `GITHUB_REPO` constant in `bearhub/data/catalog.py` backing the update check.

### Changed
- `discover_samples()` (`core/bactopia.py`) is now **strict**: it returns only
  genuine Bactopia sample folders (those containing a `main/` or `tools/`
  subdirectory) and `[]` otherwise. Previously it fell back to listing *every*
  subdirectory, so pointing the picker at e.g. `$HOME` showed dotfiles and
  unrelated folders (`.ssh`, `.cache`, …) as "samples".
- `VERSION` file is the single source of truth for the BEAR-HUB app version.

### Fixed
- `Makefile`: `install`/`update` no longer default to the stale Bactopia `3.0.0`
  pin (now `4.0.0`, matching the installer and app); `make run` now launches the
  Reflex app via `bearhub_rx/run.sh` instead of the non-existent `run_bear.sh`.

---

## [Unreleased] — refactor/improvements branch

### Added
- `constants.py` — centralized app-level constants (`GITHUB_REPO`, `APP_STATE_DIR`,
  `BACTOPIA_VERSION_PINNED`, etc.) to eliminate string duplication across modules.
- `utils/` package — split monolithic `utils.py` (~975 lines) into focused submodules:
  - `utils/data.py` — static data (MLST schemes, genome sizes); no Streamlit dependency.
  - `utils/system.py` — environment/tool detection, config loading, directory helpers.
  - `utils/fs.py` — file-system browser widget.
  - `utils/exec.py` — async subprocess execution and log streaming.
  - `utils/bactopia.py` — Bactopia-specific helpers (sample discovery, outdir guessing).
  - `utils/validation.py` — path sanitization / shell-injection prevention.
  - `utils/history.py` — SQLite-backed run history.
  - `utils/__init__.py` — backward-compatible re-exports; existing `import utils` calls
    continue to work without changes.
- `utils/validation.py` — `validate_path` and `validate_outdir` reject paths containing
  shell metacharacters (`;`, `|`, `` ` ``, `$`, `<`, `>`, etc.) before they reach
  subprocess calls.
- `utils/history.py` — SQLite database at `~/.bactopia_ui_local/run_history.db` records
  every pipeline run (page, samples, command, start/finish time, status).
- Dashboard **Recent runs** expander shows the 20 most recent runs from history.
- `utils.init_session_state()` helper added to `utils/system.py`; called at the top of
  every page to guard against `KeyError` on first load.
- `tests/` directory with a pytest suite covering:
  - `test_data.py` — ANSI regex, genome sizes, MLST schemes.
  - `test_exec.py` — log stripping and line normalization.
  - `test_validation.py` — path validation including injection attempts.
  - `test_system.py` — `which`, `run_cmd`, `discover_samples_from_outdir`.
  - `conftest.py` — shared fixtures (mock FASTQ tree, mock Bactopia output dir).
- `Makefile` with `install`, `run`, `update`, `uninstall`, `test`, `lint` targets.
- `CHANGELOG.md` (this file).
- `install_bear.sh` refactored into named functions:
  `check_prerequisites`, `setup_bear_hub_env`, `setup_bactopia_env`,
  `write_config`, `configure_streamlit`.
- `install_bear.sh` now pins Bactopia to `BACTOPIA_VERSION` (default `3.0.0`);
  override with `BACTOPIA_VERSION=X.Y.Z make install` or env var.
- `install_bear.sh` writes config to `~/.bear-hub/config.env` (new canonical location)
  and also writes a copy to `~/BEAR-HUB/.bear-hub.env` for backward compatibility.
- `utils/system.py → bootstrap_bear_env_from_file()` now also checks
  `~/.bear-hub/config.env` (new path) before the legacy locations.
- `pages/PORT.py` — full English translation (was mixed PT/EN), prominent
  "under development" warning banner, run button disabled with tooltip.
- `pages/UPDATES.py` — GitHub API rate-limit detection (`X-RateLimit-Remaining`,
  HTTP 429/403), offline mode detection (`ConnectionError`, `Timeout`), wrapped in
  `st.spinner`.
- `pages/UPDATES.py` — uses `GITHUB_REPO` from `constants.py` instead of hardcoded string.

### Changed
- `pages/BACTOPIA.py` — `preflight_validate()` now uses `validate_outdir` and
  `validate_path` for outdir and datasets path checks.
- `pages/BACTOPIA.py`, `BACTOPIA-TOOLS.py`, `MERLIN.py` — record run start/finish in
  SQLite history.
- All pages now call `utils.init_session_state()` at startup to avoid `KeyError`.

### Fixed
- `pages/BACTOPIA-TOOLS.py`, `MERLIN.py` — validate outdir before building Nextflow
  command, preventing empty/invalid paths from reaching the subprocess.

### Removed
- `utils.py` (monolithic file) — replaced by the `utils/` package; backward compat
  maintained via `utils/__init__.py`.

---

## [0.1.6] — 2025-03-XX

### Changed
- Updated README installation instructions.

---

## [0.1.5] — 2025-02-XX

### Removed
- AppImage installation method and related files.

---

## [0.1.4] — 2025-01-XX

### Fixed
- MLST scheme updates and various bug fixes.
- Bactopia parameter enhancements.

---

## [0.1.3] — 2024-12-XX

### Fixed
- Genome size parsing bug.
- FOFN generator improvements.

---

## [0.1.2] — 2024-11-XX

### Added
- Initial FOFN generator with automatic run-type detection.
- Async execution with live log tailing.

---

## [0.1.1] — 2024-10-XX

### Added
- BACTOPIA-TOOLS page for running post-processing workflows.
- MERLIN page for species-specific tools.

---

## [0.1.0] — 2024-09-XX

### Added
- Initial release.
- BACTOPIA page for running the main pipeline.
- Streamlit multi-page application structure.
- Docker-only profile enforcement.
