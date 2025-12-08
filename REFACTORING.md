# Refactoring Tips

During the documentation process, several areas of the codebase were identified that could benefit from refactoring. These changes would improve maintainability, reduce code duplication, and enhance robustness.

## 1. Code Duplication in File Browsers
**Issue**: The `_fs_browser_core` and `path_picker` functions are nearly identical across `BACTOPIA.py`, `BACTOPIA-TOOLS.py`, `MERLIN.py`, and `PORT.py`.
**Recommendation**: Extract these into a shared utility module (e.g., `utils/file_browser.py`). This would allow all pages to import and use a single source of truth for file selection logic.

## 2. Shared Async Runner Logic
**Issue**: The asynchronous execution logic (`start_async_runner_ns`, `_async_exec`, `_thread_entry`, `drain_log_queue_ns`) is duplicated across all page files.
**Recommendation**: Create a `utils/runner.py` module. Define a generic `AsyncRunner` class that handles subprocess management, log streaming, and state updates. Each page can then instantiate this class.

## 3. Environment Bootstrapping
**Issue**: The `bootstrap_bear_env_from_file` function is repeated in every file.
**Recommendation**: Move this into a `utils/env.py` module and call it once at the application entry point or lazily when needed.

## 4. Helper Functions
**Issue**: Functions like `which`, `ensure_state_dir`, `nextflow_available`, and string normalization utilities are repeated.
**Recommendation**: Consolidate these into `utils/common.py`.

## 5. Configuration Management
**Issue**: Configuration (like default directories) is hardcoded in multiple places.
**Recommendation**: Use a central configuration file or a `config.py` module to define constants like `DEFAULT_OUTDIR`, `APP_STATE_DIR`, etc.

## 6. Type Hinting
**Issue**: While some functions have type hints, coverage is inconsistent.
**Recommendation**: Apply strict type checking (mypy) across the entire codebase to catch potential errors early.

## 7. Error Handling in Nextflow Command Generation
**Issue**: Command strings are built using list concatenation.
**Recommendation**: Use a builder pattern or a dedicated class to construct Nextflow commands. This would make it easier to handle conditional flags and ensure proper quoting/escaping.
