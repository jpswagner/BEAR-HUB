# Changelog

All notable changes to BEAR-HUB are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.4] — 2026-07-21

### Fixed
- **`uninstall_bear.sh` did not remove the installation, and could target the
  wrong directories.** It derived every path from the repo's *parent*, but
  `install_bear.sh` sets `BEAR_HUB_ROOT` to the repo itself. For the standard
  clone at `~/BEAR-HUB` that resolved to `$HOME`: it offered to delete `~/data`
  and `~/bactopia_out` — directories it never created — while reporting the
  multi-GB conda envs as "not found" and leaving them on disk. It also never
  touched `~/.bactopia_ui_local`, and stopped the app with
  `pkill -f "reflex run"`, which kills unrelated Reflex apps on a shared server.

### Added
- **`uninstall_bear.sh --dry-run`** prints every path and size it would remove
  without touching disk.
- Uninstall safety rails: paths are read from `~/.bear-hub/config.env` (so a
  results directory on another disk is found), `$HOME` and system directories
  are refused outright, the script will not run without a terminal, and the
  confirmation requires typing `uninstall` rather than `y` — a piped `yes`
  cannot walk through it.

### Removed
- Legacy working-directory trees that `main` stopped tracking in 74610a7 but
  which stayed on disk, making the checkout look like it shipped three UIs:
  `pages/` and `utils/` (Streamlit), `nicegui_app/` (NiceGUI), `mockups/` (a
  329M Reflex prototype) and stray `__pycache__/`. The Streamlit and NiceGUI
  code remains on the `streamlit-legacy` and `nicegui-migration` branches.
- `.bear-hub.env` is no longer tracked. `install_bear.sh` generates it, but an
  early commit had published a developer's absolute paths along with a stale
  `BACTOPIA_VERSION="3.0.0"` pin contradicting the 4.0.0 the installer sets.

---

## [2.0.3] — 2026-07-21

### Fixed
- **`update_bear.sh` could leave the app unable to start.** It deleted the whole
  `bearhub_rx/.web/` to force a frontend rebuild, but that directory holds
  `node_modules` and Reflex never reinstalls them on the next launch. The
  production build then failed with `react-router: command not found`. The
  updater now removes only the compiled output (`build/`, `.states/`), and
  `run.sh` self-heals a missing `node_modules` on launch.
- **Status page reported Bactopia and Nextflow as `unknown`.** The app looked for
  its config at `~/.bactopia_ui_local/config.env`, but `install_bear.sh` writes
  `~/.bear-hub/config.env`. That file was never read, so `BACTOPIA_ENV_PREFIX`
  stayed unset and tool lookups fell back to `PATH` — where nothing from the
  `bactopia` conda env ever appears. Tool resolution now goes through the env
  prefix, with a repo-layout fallback so detection works even without a config.
- **Status page reported the wrong Java.** It resolved `java` from `PATH`,
  showing the distro's JDK (e.g. 11) instead of the env's (23) that Nextflow
  actually runs on — which read as a failure against the Java 17+ requirement.
  Conda JDK builds (`23.0.2-internal`) were also parsed as `unknown`.

### Added
- **GitHub link in the top bar**, on every page.

### Documentation
- README: documented the in-app **Update & verify** flow (shipped in 2.0.2 but
  undocumented); corrected the run section (frontend and backend share port
  3200 in single-port mode, not `:8200`); and fixed a troubleshooting entry that
  told users to delete the whole `.web/` — the exact action that breaks startup.

---

## [2.0.2] — 2026-07-10

### Fixed
- **Installer did not set up conda, and Reflex was sometimes missing.** Reported
  by users on machines without conda:
  - `install_bear.sh` now **auto-installs Miniforge** (conda + mamba,
    conda-forge default) when neither conda nor mamba is found — instead of
    printing instructions and exiting. It also detects a conda living in a common
    prefix (`~/miniforge3`, `~/miniconda3`, `~/anaconda3`, `~/mambaforge`) not on
    `PATH`. Set `BEAR_HUB_SKIP_CONDA_BOOTSTRAP=1` to opt out.
  - The Reflex install now runs **idempotently on every install/update** (was
    only on first env creation), so a partial install where the env exists but
    Reflex is missing is repaired, and `update_bear.sh` can bump Reflex when a
    release requires it. Reflex is pinned via a single `REFLEX_VERSION` var.
  - `setup_bactopia_env` checks for the actual `bactopia` binary (not just the
    env dir) and **repairs** an incomplete env with `conda install` instead of
    silently skipping.

---

## [2.0.1] — 2026-06-26

### Fixed
- **Fresh-machine installs failing with "missing conda / reflex".** The install
  and launch scripts were tied to one machine's layout; on any other clone path
  or username the app couldn't find its environment:
  - `install_bear.sh` now derives `BEAR_HUB_ROOT` from the script's own location
    (was hardcoded to `$HOME/BEAR-HUB`), so the installer works wherever the repo
    is cloned. An explicit `BEAR_HUB_ROOT` env var still overrides.
  - Fixed a doubled path (`…/BEAR-HUB/BEAR-HUB/bearhub_rx`) that made the Reflex
    pre-compile silently skip and the printed "Next steps" point at a missing dir.
  - Both the installer and `bearhub_rx/run.sh` now launch Reflex via
    `python -m reflex` instead of the `bin/reflex` shim, whose pip-generated
    shebang hardcodes an absolute interpreter path and breaks when the env moves.
  - `run.sh` resolves the env's Python by path and no longer relies on
    `conda run -n bear-hub` (the envs are prefix envs, so the named lookup never
    matched) or on `conda`/`reflex` being on `PATH` at runtime.
  - The installer's verify step (Step 6) now runs `python -m reflex --version` —
    exercising the real launch path — instead of only `import reflex`, so a broken
    launcher fails the smoke test.

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
