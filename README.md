<p align="center">
<img width="360" alt="BEAR-HUB Logo" src="https://github.com/user-attachments/assets/6d23dc4b-fc4d-4fa7-9b2a-e55adb623598" />
</p>

# 🐻 BEAR-HUB
**Bacterial Epidemiology & AMR Reporter — HUB**

A web UI (built with **Reflex**) that orchestrates the **Bactopia 4.0** bacterial
genomics pipeline (**Nextflow + Docker**). Scan reads → build a sample sheet →
QC, assembly, annotation and typing → run Bactopia Tools and MERLIN — without
touching the command line.

**Features:** main pipeline (PE / single-end / ONT / hybrid / assembly, with auto
run-type detection + editable sample sheet), Bactopia Tools (`--wf`), MERLIN,
parameter presets, live run monitor + history.

---

## 1. Requirements

Linux (Ubuntu-like). The installer sets up everything else in two local conda
environments.

- **Docker** with the daemon running (Bactopia runs with `-profile docker`)
- Internet access (conda/pip packages + container images) and free disk space
- **conda / mamba** — *optional*: if neither is found, the installer auto-installs
  Miniforge (set `BEAR_HUB_SKIP_CONDA_BOOTSTRAP=1` to require a pre-existing conda)

> Java and Nextflow are installed automatically inside the `bactopia` env; Reflex
> is installed into the `bear-hub` env. Nothing else is needed system-wide.

---

## 2. Install

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
bash install_bear.sh
```

This creates two conda envs (`bear-hub` for the UI, `bactopia` for the pipeline),
pins **Bactopia 4.0.0**, writes `~/.bear-hub/config.env`, and ends with a
verification step (**Step 6**) that checks Reflex, Java, Nextflow, Bactopia and
the Docker daemon. A clean install must finish with `✓ Core dependencies verified.`

## 3. Run

```bash
bash bearhub_rx/run.sh
```

Then open **http://localhost:3200**. The first launch compiles the frontend
(~1–2 min); later launches are fast. Frontend and backend share port **3200**
(production single-port mode).

## 4. Update

**From the app (easiest).** Open the **Status** page → **Update & verify**. It
confirms first (warning you if runs are active, since updating stops the app),
then pulls, re-runs the installer, relaunches, and keeps the full output in a
**Last update log** panel so you can review what changed. The same page shows an
"Update available" banner when a newer release exists on GitHub.

**From the terminal.**

```bash
bash update_bear.sh      # or: make update
```

Either route does the same thing: stops the running app, stashes any local
changes (restored at the end), fast-forward pulls, re-runs the installer
(keeping the Bactopia version you already installed), and clears the compiled
frontend so it rebuilds on next launch — while keeping `.web/node_modules`.

## 5. Uninstall

```bash
bash uninstall_bear.sh --dry-run   # show exactly what would be removed
bash uninstall_bear.sh             # then do it, prompting per item
```

Prompts separately for the conda envs, the config (`~/.bear-hub`), the app state
(`~/.bactopia_ui_local`), your data and results, and finally the repo itself —
printing each path and its size first. Paths come from `~/.bear-hub/config.env`,
so a results directory on another disk is found rather than missed.

It refuses to run without a terminal and asks you to type `uninstall`, so a
piped `yes` cannot walk through it. Nextflow's own `~/.nextflow` cache is left
alone, since it is shared with any other Nextflow use on the machine.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| **Run fails instantly / red "Docker daemon not running" banner** | Start Docker: `sudo systemctl start docker`. Add your user once: `sudo usermod -aG docker "$USER"` then log out/in. |
| **`install_bear.sh` Step 6 says Java/Nextflow FAIL** | The `bactopia` env didn't get a JDK/Nextflow. Re-run the installer, or `<repo>/envs/bactopia/bin/nextflow -version`. |
| **Status page shows Bactopia / Nextflow as `unknown`** | Fixed in **v2.0.3**. Those tools live in `<repo>/envs/bactopia/bin/` and are never on `PATH`, so the app reads their location from `~/.bear-hub/config.env` — re-run `bash install_bear.sh` if that file is missing. |
| **Reflex won't install / "missing conda"** | The installer auto-installs Miniforge if conda is absent, then pip-installs Reflex (idempotent — re-run `bash install_bear.sh` to repair a partial install). Reflex ships on **PyPI, not conda**; by hand: `<repo>/envs/bear-hub/bin/python -m pip install reflex==0.9.3`. |
| **`http://localhost:3200` doesn't load** | First run is still compiling — wait for `App running at...` in the terminal. Check nothing else uses port **3200**. |
| **Page is blank / stale after an update** | Stop `run.sh`, delete `bearhub_rx/.web/build/` (**not** the whole `.web/` — it holds `node_modules`), relaunch (it rebuilds). |
| **`react-router: command not found` after an update** | `.web/node_modules` was wiped. `run.sh` reinstalls it automatically on the next launch; if that fails: `cd bearhub_rx/.web && bun install`. |
| **`Parameter ... is not declared` / `Path string cannot be empty`** | Pipeline/Bactopia version mismatch — BEAR-HUB targets **Bactopia 4.0.0** (needs **Nextflow ≥ 26.04**). Confirm both in the **Status** page. |
| **A Tool needs a database (e.g. `mlst_db`)** | Some `--wf` tools require an external DB. Provide its path in the tool's **db** field (Browse), or via the global *Extra args* box. |
| **MLST scheme dropdown only shows `(auto/none)`** | Schemes load from `bearhub_rx/bearhub/data/static.py`; auto-detection still works without picking one. |
| **A run shows "running" forever after a restart** | The **Runs** page marks orphaned runs as stale on load; click **Refresh**. |

Check installed versions any time on the **Status** page (Bactopia / Nextflow /
Java / Docker).

---

## Legacy (Streamlit)

The previous Streamlit interface is preserved on the **`streamlit-legacy`**
branch. `main` is the current Reflex app.

## License & Disclaimer

MIT License. BEAR-HUB is an **unofficial** UI for
[Bactopia](https://github.com/bactopia), maintained independently by its authors
— all credit for the analysis pipelines goes to the Bactopia team.

*Developed by João Pedro Stepan Wagner.*
