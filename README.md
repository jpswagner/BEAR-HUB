<p align="center">
<img width="480" height="480" alt="BEAR-HUB Logo" src="https://github.com/user-attachments/assets/6d23dc4b-fc4d-4fa7-9b2a-e55adb623598" />
</p>

# 🐻 BEAR-HUB  
**Bacterial Epidemiology & AMR Reporter — HUB**

BEAR-HUB is a streamlined **Streamlit** interface designed to orchestrate bacterial epidemiology and antimicrobial resistance (AMR) pipelines. It serves as a user-friendly wrapper around powerful command-line tools, primarily **Bactopia** and **Nextflow**.

## Key Features

-   **Bactopia Pipeline**: Run the complete Bactopia pipeline with automatic run-type detection (Paired-End, Single-End, Hybrid, ONT, Assembly).
-       -   **FOFN Generator**: Automatic generation of "File of File Names" for sample management.
-   **Bactopia Tools**: Execute specific post-processing workflows (e.g., AMRFinderPlus, MLST, Pan-genome analysis) on completed samples.
-   **Merlin**: Access species-specific tools and workflows.
-   **PORT**: (In Development) Support for plasmid-focused outbreak investigations using Nanopore/Hybrid assemblies.

---

## 1. Requirements

BEAR-HUB is designed for **Linux** environments (Ubuntu-like).

**Prerequisites:**

-   [x] **Conda** (Miniconda, Anaconda, or Mambaforge)
-   [x] **Internet Access** (for downloading packages and datasets)
-   [x] **Disk Space** (Bactopia and its datasets can require significant storage)
-   [x] **Docker** (Highly recommended; required for `profile: docker`)

> **Note:** While Singularity/Apptainer is supported by Nextflow, this hub is optimized for running bactopia with Docker.

---

## 2. Installation (Quick Start)

The recommended installation method is via Conda using the provided script.

### 2.1. Clone the Repository

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

### 2.2. Install Dependencies

Run the installation script to set up the Conda environments (`bear-hub` and `bactopia`) and configuration files.

```bash
chmod +x install_bear.sh run_bear.sh
./install_bear.sh
```

**What this script does:**
1.  Creates the `bear-hub` environment (Python, Streamlit, etc.).
2.  Creates the `bactopia` environment (Nextflow, Bactopia).
3.  Generates a configuration file `${HOME}/BEAR-HUB/.bear-hub.env`.

---

## 3. Usage

### 3.1. Launching the App

Start the application using the runner script:

```bash
./run_bear.sh
```

This will launch the Streamlit server and provide a local URL (usually `http://localhost:8501`). Open this URL in your web browser.

### 3.2. Navigation

-   **Home**: Dashboard overview and system health checks (Nextflow/Docker status).
-   **BACTOPIA**: The core pipeline runner. Use this to process raw reads.
    -   *Step 1*: Use "Generate FOFN" to scan your data folder and create a `samples.txt`.
    -   *Step 2*: Configure parameters (FastP, Unicycler, Resources).
    -   *Step 3*: Click "Run".
-   **BACTOPIA TOOLS**: Run specific analyses on already processed samples.
    -   Select your Bactopia output folder.
    -   Choose tools (e.g., `amrfinderplus`, `rgi`, `mlst`).
    -   Click "Run Tools".
-   **MERLIN**: Specialized tools for specific species (e.g., *Klebsiella*, *Salmonella*).
    -   Select your Bactopia output folder.
    -   Choose tools.
    -   Click "Run".
-   **PORT**: (Beta) Nanopore and plasmid analysis workflows.

---

## 4. Project Structure

```text
BEAR-HUB/
├── BEAR-HUB.py          # Main entry point (Dashboard)
├── pages/               # Sub-pages for the application
│   ├── BACTOPIA.py      # Main Bactopia pipeline interface
│   ├── BACTOPIA-TOOLS.py# Post-processing tools interface
│   ├── MERLIN.py        # Species-specific workflows
│   └── PORT.py          # Plasmid/Nanopore interface
├── static/              # Images and assets
├── install_bear.sh      # Installation script
├── run_bear.sh          # Launcher script
└── ...
```

---

## 5. Updates & Uninstallation

**Update:**
Pull the latest changes from GitHub:
```bash
git pull origin main
```
If dependencies changed, re-run `./install_bear.sh`.

**Uninstall:**
Remove the conda environments and the project folder:
```bash
conda remove -n bear-hub --all
conda remove -n bactopia --all
rm -rf ~/BEAR-HUB
```

---

## License & Disclaimer

**License**: MIT License.

**Disclaimer**:
> **BEAR-HUB** is an unofficial interface for **Bactopia** (https://github.com/bactopia).
> Bactopia is developed and maintained by its original authors. We have no official affiliation with the Bactopia project.
> All credit for the underlying analysis pipelines goes to the Bactopia team.

---

*Developed by João Pedro Stepan Wagner.*
