# BEAR-HUB — Refactor Plan

This plan captures the improvements identified during the code review and the order in which they will be implemented. The goal is to take the current Bactopia-only hub and make it genuinely extensible for tools #5, #6, #7… while tightening the UX for the tools already in it.

The work is incremental. Each step leaves the app in a runnable state and can be merged independently.

---

## Guiding principles

- **No behaviour changes** in Steps 1–3. They are structural / cleanup only.
- **One source of truth** per concern (tool list, state dir, outdir default, preset logic).
- **Convention over configuration**: every new page should need ~10 lines of boilerplate, not 60.
- **Don't rewrite the big forms** — they work. Wrap them in structure, move shared logic out, leave internals alone.

---

## Step 1 — Tool registry + `init_page` helper (structural, highest ROI)

### Why

`BEAR-HUB.py` hardcodes every tool four times (page path constants, missing-page checks, card markup, nav buttons). `MERLIN.py` re-declares the same list. Adding tool #5 today means editing 3+ files and copy-pasting card markup. Page boilerplate (APP_ROOT / PROJECT_ROOT / `bootstrap_bear_env_from_file` / `ensure_nxf_home` / `set_page_config`) is duplicated in all 5 pages.

### What

1. Create `tools.yaml` at project root — single source of truth describing every tool:
   ```yaml
   - id: bactopia
     name: Bactopia
     tagline: Main Pipeline
     page: pages/BACTOPIA.py
     icon: "🦠"
     status: stable        # stable | beta | wip
     category: pipeline
     description: >
       Builds a FOFN and runs Bactopia via Nextflow (async).
   ```
2. Create `utils/registry.py` — thin YAML loader returning a list of frozen `Tool` dataclasses.
3. Create `utils/page.py` — `init_page(title, icon, ns, defaults)` that wraps: `st.set_page_config`, project-root discovery, `bootstrap_bear_env_from_file`, `ensure_nxf_home`, `init_session_state`. Also exposes `render_tool_sidebar(current_id)` for Step 4.
4. Refactor `BEAR-HUB.py` hub:
   - Replace the hardcoded PAGE_\* constants and card blocks with a loop over `load_tools()`.
   - Status badges (🚧 for `wip`, 🧪 for `beta`) replace the manual "(IN DEVELOPMENT)" captions.
   - `missing-page` check collapses to a comprehension.
5. Refactor every page to start with `init_page(...)` — removing ~50 lines of boilerplate per page.

### Files touched

- `tools.yaml` (new)
- `utils/registry.py` (new)
- `utils/page.py` (new)
- `utils/__init__.py` (export `load_tools`, `init_page`)
- `BEAR-HUB.py` (rewrite hub section)
- `pages/BACTOPIA.py`, `pages/BACTOPIA-TOOLS.py`, `pages/MERLIN.py`, `pages/PORT.py`, `pages/UPDATES.py` (replace page header boilerplate)

### Risk

Low. Registry is additive; `init_page` wraps existing calls in the same order, so behaviour is identical.

---

## Step 2 — Consolidate constants

### Why

- `APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"` is defined in `constants.py` **and** re-declared verbatim in `pages/BACTOPIA.py:66`, `pages/MERLIN.py:63`, `pages/PORT.py:54`.
- `DEFAULT_OUTDIR` logic diverges per page: BACTOPIA uses `BASE_DIR / bactopia_out`, MERLIN hardcodes `~/BEAR_DATA/bactopia_out`, PORT uses `cwd / bactopia_out`. That divergence bites.
- PORT has `DEFAULT_BACTOPIA_OUTDIR` separate from `DEFAULT_PORT_OUTDIR`; fine to keep the second, but the first should use the shared default.

### What

1. Add `DEFAULT_OUTDIR` to `constants.py`, respecting `$BEAR_HUB_OUTDIR` and `$BEAR_HUB_BASEDIR` env vars (same precedence as current BACTOPIA).
2. Delete the per-page re-declarations. Import from `constants`.
3. Export a small `get_default_outdir()` helper if env-var-dependent logic is needed after import time (Streamlit re-imports modules on rerun, so literal constants work too).

### Files touched

- `constants.py` (add DEFAULT_OUTDIR logic)
- `pages/BACTOPIA.py`, `pages/MERLIN.py`, `pages/BACTOPIA-TOOLS.py`, `pages/PORT.py` (delete dupes, import from constants)

### Risk

Low. Mechanical replacement.

---

## Step 3 — `PresetManager` abstraction

### Why

`pages/BACTOPIA.py:120-266` is ~150 lines of preset machinery (load/save/apply/delete + callbacks + sidebar). Right now only Bactopia has presets. Bactopia-Tools, Merlin, and PORT all need the same feature eventually — copy-pasting this code three more times is the wrong answer.

### What

1. Create `utils/presets.py` with a `PresetManager(ns, allowed_keys, presets_path)` class:
   - `.load()` / `.save(name)` / `.apply_pending()` — same semantics as today.
   - `.render_sidebar()` — renders the "Load / Save / Delete" block.
   - Uses per-page preset files: `~/.bactopia_ui_local/presets_<ns>.yaml` (so Bactopia presets don't collide with future Tools presets).
2. Migrate Bactopia's existing `~/.bactopia_ui_local/presets.yaml` → `presets_bactopia.yaml` on first load (one-time rename, fall back to reading old file if new one missing).
3. Rewrite BACTOPIA.py's preset section to ~5 lines:
   ```python
   preset_mgr = PresetManager("bactopia", PRESET_KEYS_ALLOWLIST)
   preset_mgr.apply_pending()
   # … later, in sidebar:
   preset_mgr.render_sidebar()
   ```
4. **Don't yet** wire it into other pages — that's a separate Step 3b once Bactopia proves the abstraction.

### Files touched

- `utils/presets.py` (new)
- `utils/__init__.py` (export `PresetManager`)
- `pages/BACTOPIA.py` (~150 lines deleted, ~10 added)

### Risk

Medium. Preset semantics around "stage then apply on next rerun" must be preserved exactly. Test: save preset → load preset → verify all widgets reflect loaded values.

---

## Step 4 — Sidebar nav + form organization polish

### Why

- Currently users must go back to the hub to switch pages. No in-page nav exists.
- `BACTOPIA.py` (1640 lines) and `BACTOPIA-TOOLS.py` (1416 lines) mostly already use `st.expander`, but: top of page shows no overview, some sections sit outside expanders, and there's no consistent "section header" pattern across the two pages.
- `.streamlit/config.toml` has `showSidebarNavigation` commented out — decide on one mode.

### What

1. `render_tool_sidebar(current_id)` in `utils/page.py`:
   - Links to every tool (from registry), with current one highlighted.
   - "← Hub" button at top.
   - Shows environment badges (Nextflow / Docker) — reuses logic currently inline in `BACTOPIA.py:525-561`.
2. Call it from every page via `init_page(...)`.
3. Small form-organization polish (no rip-outs):
   - In `BACTOPIA.py`, wrap the "Extra parameters (raw line)" text input in an expander so it stops crowding the top-level flow.
   - Ensure every major section in `BACTOPIA.py` and `BACTOPIA-TOOLS.py` uses `st.expander(..., expanded=False)` by default except the execution panel.
4. Decide on `showSidebarNavigation` — disable Streamlit's auto nav (since we're providing our own) and document it.

### Files touched

- `utils/page.py` (add `render_tool_sidebar`)
- `.streamlit/config.toml` (set `showSidebarNavigation = false`, prune commented noise)
- `pages/BACTOPIA.py` (strip inline env-badge block, wrap one stray text_input, call `render_tool_sidebar`)
- Other pages: picked up automatically via `init_page`

### Risk

Low-medium. Streamlit sidebar markup is reasonably stable. Keep existing `render_presets_sidebar()` alongside the new nav — they compose, they don't conflict.

---

## Step 5 — Run-history polish

### Why

- `record_run_finish` is currently called on every page's running loop (`pages/PORT.py:457`, `pages/BACTOPIA.py:1618`, `pages/BACTOPIA-TOOLS.py:1374`, need to verify `pages/MERLIN.py`). Some paths may leave rows stuck in `running` on errors / page reloads.
- The hub's Recent-runs expander (`BEAR-HUB.py:197-205`) shows only 5 columns and drops the `command` field despite recording it.
- No duration, no re-run button, no per-module filter, no link to the run's outdir.

### What

1. Audit `record_run_finish` call sites; ensure every page passes `success=(rc==0)` (today it hardcodes `True` — so history currently lies when a run fails).
2. Extend `utils/history.py`:
   - Add `stale_cleanup()` that marks rows older than N hours still in `running` as `interrupted` on app start.
   - Expose duration as a derived column.
3. Rewrite the Recent-runs section on the hub:
   - Show Started / Duration / Module / Samples / Status.
   - Module dropdown filter (driven by registry IDs).
   - "Show command" expander per row.
   - "Re-run" button that switches to the page and stages a preset named `__rerun_<id>` (piggy-backing on the preset system).
4. Pass true success flag from `check_status_and_finalize_ns`. Currently it doesn't return the rc — extend its signature to return `(finished, success)`.

### Files touched

- `utils/history.py` (add stale_cleanup, duration helper)
- `utils/exec.py` (return success flag from `check_status_and_finalize_ns`)
- `BEAR-HUB.py` (rewrite Recent-runs)
- All pages (pass real success flag to `record_run_finish`)

### Risk

Medium. Touching `check_status_and_finalize_ns` is shared infra — a regression here breaks every page's run loop. Keep the old signature backward-compatible if possible.

---

## Minor polish (applied across steps)

- `pages/PORT.py:42`: `page_title="BEAR-HUB"` → `"BEAR-HUB — PORT"`.
- `pages/PORT.py:41`: "Config geral" comment → English.
- `BEAR-HUB.py:114-124`: commented-out env diagnostics. Either delete (recommended) or move to `render_tool_sidebar()`. Plan: delete — the sidebar badges from Step 4 replace them.
- `BEAR-HUB.py:208-225`: footer is PT + EN. Move to `README.md` / About page, drop from every hub page-load.
- `.streamlit/config.toml`: trim to active settings only.
- `pages/BACTOPIA.py:66`: delete duplicated `APP_STATE_DIR` / `PRESETS_FILE` (absorbed by Step 2 + Step 3).

## Explicitly out of scope

- **Page-level session-state namespacing** (`bactopia_profile` vs bare `profile`). Too invasive for a pass focused on structure; would touch hundreds of widget keys. Defer.
- **i18n library (gettext/babel)**. Overkill for one PT disclaimer. Drop PT or keep as a side note.
- **Form layout rewrite** for BACTOPIA-TOOLS.py / BACTOPIA.py. They work; structural wrapping is enough until a real UX regression is reported.
- **Path validation everywhere**. `validate_path` already exists; full audit is a separate pass.
- **Log-box streaming refactor** (components.html re-render every tick). Only matters at 10k+ log lines — premature.

---

## Order & rough effort

| # | Step | Effort | Risk |
|---|---|---|---|
| 1 | Tool registry + `init_page` | ~2h | Low |
| 2 | Consolidate constants | ~30m | Low |
| 3 | `PresetManager` | ~1.5h | Medium |
| 4 | Sidebar nav + form polish | ~1.5h | Low-medium |
| 5 | Run-history polish | ~1.5h | Medium |
| — | Minor fixes | ~30m | Low |

Total: ~7 hours of focused work. Each step is a self-contained PR-sized change.
