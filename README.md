<p align="center">
<img width="480" height="480" alt="BEAR-HUB Logo" src="https://github.com/user-attachments/assets/6d23dc4b-fc4d-4fa7-9b2a-e55adb623598" />
</p>

# 🐻 BEAR-HUB  
**Bacterial Epidemiology & AMR Reporter — HUB**

BEAR-HUB is a streamlined **Streamlit** interface designed to orchestrate bacterial epidemiology and antimicrobial resistance (AMR) pipelines. It serves as a user-friendly wrapper around powerful command-line tools, primarily **Bactopia** and **Nextflow**.

## Key Features

-   **Bactopia Pipeline**: Run the complete Bactopia pipeline with automatic run-type detection (Paired-End, Single-End, Hybrid, ONT, Assembly).
    -   **FOFN Generator**: Automatic generation of "File of File Names" for sample management.
-   **Bactopia Tools**: Execute specific post-processing workflows (e.g., AMRFinderPlus, MLST, Pan-genome analysis) on completed samples.
-   **Merlin**: Access species-specific tools and workflows.
-   **PORT**: (In Development) Support for plasmid-focused outbreak investigations using Nanopore/Hybrid assemblies.

---

## 1. Requirements

BEAR-HUB is designed for **Linux** environments (Ubuntu-like).

**Prerequisites:**

-   [x] **Conda** (Miniconda, Anaconda, or Mambaforge) - Required for managing bioinformatics environments.
-   [x] **Docker** (Highly recommended; required for `profile: docker`) - Required for running Bactopia containers.
-   [x] **Internet Access** (for downloading packages and datasets)
-   [x] **Disk Space** (Bactopia and its datasets can require significant storage)

> **Note:** While Singularity/Apptainer is supported by Nextflow, this hub is optimized for running bactopia with Docker.

---

## 2. Installation

We provide shell scripts to automate the setup of Conda environments (`bear-hub` and `bactopia`) directly from the source code.

### 2.1. Clone the Repository

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

### 2.2. Install Environment

```bash
chmod +x install_bear.sh
./install_bear.sh
```

### 2.3. Run the Application
Use the launcher script to start the interface.

```bash
chmod +x run_bear.sh
./run_bear.sh
```
This will activate the `bear-hub` environment and launch Streamlit in your default web browser.

### 2.4. Uninstall
To uninstall the application, you can use the provided uninstaller script:

```bash
chmod +x uninstall_bear.sh
./uninstall_bear.sh
```
This script will help you remove the configuration folders and optionally the `bear-hub` and `bactopia` Conda environments. Finally, you can delete the repository directory manually.

---

## 3. Usage & Navigation

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

## 4. Updates

A dedicated **Updates** page allows you to keep BEAR-HUB and its dependencies up to date.

*   **Location**: Dashboard (Home) -> "System" -> "Updates & Status".
*   **Features**:
    *   View current versions of BEAR-HUB, Bactopia, Nextflow, and Docker.
    *   **Update BEAR-HUB (Git Only)**: Pulls the latest code from the repository.
    *   **Update BEAR-HUB (Full)**: Pulls code and updates Python dependencies (`pip install`).
    *   **Update Bactopia Env**: Updates the conda environment used by the pipeline.

> **⚠️ Warning**: Only run updates if you have appropriate system permissions (write access to the installation folder and conda environments). This is especially important for multi-user deployments.

---

## License & Disclaimer

**License**: MIT License.

**Disclaimer**:
> **BEAR-HUB** is an unofficial interface for **Bactopia** (https://github.com/bactopia).
> Bactopia is developed and maintained by its original authors. We have no official affiliation with the Bactopia project.
> All credit for the underlying analysis pipelines goes to the Bactopia team.

---

*Developed by João Pedro Stepan Wagner.*
