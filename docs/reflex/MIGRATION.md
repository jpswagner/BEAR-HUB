# BEAR-HUB → Reflex migration & recovery guide

This is the handoff for porting the Streamlit BEAR-HUB to **Reflex** (`bearhub_rx/`),
written so any Claude Code session — including from the phone / `claude.ai/code` — can
continue without the prior conversation.

## 0. Read this first — what state we're in

- The Reflex app's Python **source was lost** (it was never committed; only `.pyc`
  bytecode survived in `bearhub_rx/bearhub/**/__pycache__/`).
- It has been **recovered by decompilation** into `bearhub_rx/_recovered/`:
  - `_recovered/src/` — best-effort decompiled `.py` (Python 3.10 bytecode, via `pycdc`).
    **Reference only — not runnable.** Some functions show `# WARNING: Decompyle incomplete`.
    (This is the only recovery kept on `dev`.)
  - `_recovered/bytecode/` + `_recovered/disasm/` — raw `.pyc` (re-decompilable) and full
    `pycdas` disassembly of the latest 3.11 build; authoritative when `src/` has a gap.
    **Archived on the `reflex` branch** (kept off `dev`):
    `git checkout reflex -- bearhub_rx/_recovered/bytecode bearhub_rx/_recovered/disasm`
  - `bearhub_rx/bearhub/data/` — the only source that survived intact (`catalog.py`,
    `help_texts.py`). **Trust these directly.**
- The Streamlit app (`pages/BACTOPIA.py`, `utils/`) is the **working, authoritative**
  behaviour to port from. Two param bugs already fixed there; one documented. See
  [`../bactopia/PARAM_AUDIT.md`](../bactopia/PARAM_AUDIT.md).

## 1. Recovered Reflex architecture (this is the target shape)

From the decompiled `state.py` + module layout, the intended structure is clean and worth keeping:

```
bearhub_rx/
  rxconfig.py
  bearhub/
    bearhub.py            # app entry: registers pages
    state.py              # Reflex state: WizardMixin + ToolsState/MerlinState/BactopiaState
    core/
      system.py           # nextflow_available(), get_default_outdir(), env bootstrap
      bactopia.py         # FS helpers: discover_samples(), guess_root_default(), safe_dir()  (mirror of utils/bactopia.py)
      fofn.py             # build the samples.txt FOFN + write_include_file()
      runner.py           # nextflow_wf_cmd(), join_subcommands(), background run + log stream, stop()
    components/
      wizard.py           # the GUIDED-RUNS stepper (the key UX difference vs Streamlit)
      shell.py            # page shell / layout
      help.py             # help/expander text
    pages/
      hub.py  bactopia.py  tools.py  merlin.py  status.py
    data/
      catalog.py          # SURVIVED — FIELD_SPECS + build_tool_args() for Bactopia Tools
      help_texts.py       # SURVIVED
```

### `state.py` shape (recovered)
- **`WizardMixin`** (shared mixin): `step` nav (`next_step/prev_step/goto`), `outdir` +
  directory picker (`open_picker_for/picker_enter/picker_up/picker_home/picker_select`),
  sample discovery + selection (`scan`, `toggle_sample`, `select_all_samples`), general
  Nextflow params (`profile/threads/memory/resume/extra`), and live runner state
  (`log/status/running`, `status_label`, `status_color`, `log_text`), plus `merged` results.
- **`ToolsState(rx.State, WizardMixin)`** — Bactopia Tools page. Holds `picks/opts/flags`
  seeded from `catalog.DEFAULT_OPTS/DEFAULT_FLAGS`; `preview()` and `_build()` call
  `catalog.build_tool_args()` + `runner.nextflow_wf_cmd()`; `run()` is an `rx.event(background=True)`.
- **`MerlinState`** — same pattern over `catalog.MERLIN_WF_IDS`.
- **Bactopia main-pipeline state** — defined at the bottom of `state.py` (the
  `_ASSEMBLY_MODES` / `_MODE_IMPLIED` block). The decompiler **truncated this** — it is the
  part that builds the main `bactopia` command, i.e. exactly where the param bugs live.
  **Rebuild it from `pages/BACTOPIA.py` (already fixed), not from the bytecode.**

## 2. The "guided set of runs" (why Reflex)

The differentiator is `components/wizard.py`: a **step-by-step wizard** (pick outdir →
scan/select samples → choose tools/assembly mode → review command → run + watch log)
instead of Streamlit's one-long-form page. The `WizardMixin.step` machinery drives it.
Preserve this stepper model — it's the reason for the port.

## 3. Do this during the port: one framework-agnostic param/command core

The bug class (`unicycler_opts`, `skip_qc_plot`, `short_polish`) exists because command
building was **duplicated** inside each UI (Streamlit page, and again in Reflex `state.py`)
and drifted from Bactopia's real param names. **Fix it structurally:**

- Put **all** command/param logic in pure-Python `core/` (no `streamlit`, no `reflex`
  imports): `core/fofn.py`, `core/runner.py`, and a new `core/bactopia_cmd.py` for the
  main-pipeline builder. The Streamlit `data/catalog.py` pattern (declarative `FIELD_SPECS`
  + a pure `build_*_args()`) is the model — extend it to the main pipeline.
- UIs (Streamlit page or Reflex state) only collect values and call the core builder.
- **Validate every param name** against `docs/bactopia/bactopia_params_v4.0.0.json`. Add a
  tiny unit test that asserts each emitted `--flag` ∈ that set — this would have caught all 3 bugs.

## 4. Preserve the programmed defaults (do not regress these)

BEAR-HUB intentionally overrides some Bactopia defaults. Carry these into the port exactly:

| BEAR-HUB control | flag | BEAR-HUB default | Bactopia default |
|---|---|---|---|
| Min Contig Len (all assemblers; also Unicycler `--min_fasta_length`) | `--min_contig_len` | **1000** (always emitted) | 500 |
| Min Coverage | `--min_contig_cov` | **10** | 2 |
| AMRFinder ident | `--ident_min` | **0.9** | -1 |
| AMRFinder coverage | `--coverage_min` | **0.6** | 0.5 |
| Unicycler mode | `--unicycler_mode` | normal (always emitted when Unicycler active) | normal |
| Skip QC plots | `--skip_qc_plots` | **True** | false |

## 5. Continuing from the phone / web

- Active development lives on the **`dev` branch** (pushed to GitHub); `main` is left
  untouched. The raw recovery archive (bytecode + disassembly) is parked on the **`reflex`**
  branch. Open `dev` from `claude.ai/code` or the Claude mobile app to keep editing with
  full repo context.
- `/remote-control` mirrors a running CLI session to the web/phone, but a *fresh* mobile
  session won't have the chat history — it will have **this doc + the recovered tree +
  the param audit**, which is the durable context. Start by reading this file.

## 6. Suggested next steps (in order)

1. Rebuild `core/` as pure-Python from `_recovered/` + Streamlit source; get `bearhub_rx`
   importing again (`reflex run`).
2. Implement `core/bactopia_cmd.py` from the **fixed** `pages/BACTOPIA.py`; wire the
   `--hybrid`/`--short_polish` fix via the FOFN `runtype` column (see PARAM_AUDIT §bugs).
3. Add the param-name validation test.
4. Then expand coverage using PARAM_AUDIT's ⬜ list (QC gates first).

## 7. UI changes (reconstruct pages to clean source as we touch them)

Pages run from bytecode until edited; each UI change requires rebuilding that page's
`.py` from the disassembly (`pycdas`) + the live screenshots, then it shadows the `.pyc`.

- [x] **Hub — equal-size cards.** `pages/hub.py`: cards differed in height by description
  length. Fix = `height="100%"` on each card's `rx.link`/`rx.card` + `align="stretch"` and
  `style={"gridAutoRows": "1fr"}` on the `rx.grid`, so all four cards match.
- [x] **Main pipeline — split "Typing & extras".** `pages/bactopia.py`: the old step 4
  bundled typing (AMRFinderPlus, MLST, datasets) with execution extras (general params,
  Nextflow reports, raw extras). Split into **"Typing"** (step 4) and **"Extras"** (step 5);
  `STEPS` is now 6 entries and `bactopia_page()`'s `rx.match` maps `0..5`. The `WizardMixin`
  state tracks `step` as a plain int (no hardcoded count), so no state change was needed.

When a page is rebuilt to clean source, drop its `.pyc` from the materialisation set.
