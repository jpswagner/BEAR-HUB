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

- **conda** or **mamba** (Miniconda / Mambaforge)
- **Docker** with the daemon running (Bactopia runs with `-profile docker`)
- Internet access (conda/pip packages + container images) and free disk space

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
(~1–2 min); later launches are fast. Backend runs on `:8200`.

## 4. Uninstall

```bash
bash uninstall_bear.sh
```

Removes the conda envs and config (with prompts). Delete the repo folder to
finish.

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| **Run fails instantly / red "Docker daemon not running" banner** | Start Docker: `sudo systemctl start docker`. Add your user once: `sudo usermod -aG docker "$USER"` then log out/in. |
| **`install_bear.sh` Step 6 says Java/Nextflow FAIL** | The `bactopia` env didn't get a JDK/Nextflow. Re-run the installer, or `conda run -p ~/BEAR-HUB/envs/bactopia nextflow -version`. |
| **Reflex won't install** | Reflex ships on **PyPI, not conda**; the installer pip-installs it. If you build the env by hand: `~/BEAR-HUB/envs/bear-hub/bin/pip install reflex==0.9.3`. |
| **`http://localhost:3200` doesn't load** | First run is still compiling — wait for `App running at...` in the terminal. Check nothing else uses ports **3200/8200**. |
| **Page is blank / stale after an update** | Stop `run.sh`, delete `bearhub_rx/.web/`, relaunch (it rebuilds). |
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
