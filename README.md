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

## 2. Installation (Recommended: AppImage)

For most users, we recommend downloading the **AppImage**. This is a single file that contains the application and can be run without installing Python libraries manually.

### 2.1. Download
Go to the [**Releases Page**](https://github.com/jpswagner/BEAR-HUB/releases) and download the file ending in `.AppImage` (e.g., `BEAR-HUB-x86_64.AppImage`).

### 2.2. Run
1.  Right-click the downloaded file -> **Properties** -> **Permissions**.
2.  Check the box **"Allow executing file as program"** (or similar).
3.  Double-click the file to run.

**First Run Setup:**
*   On the first run, the app will ask if you want to create a **Desktop Shortcut**. We recommend clicking "Yes".
*   It will then open a terminal window to check for Docker and Conda and set up the necessary environments. This setup happens only once.
*   The setup process logs to `~/BEAR-HUB/install.log`.
*   Once finished, the application will launch in your default web browser.

---

## 3. Manual Installation (Source Code)

If you are a developer or prefer to run the code directly from the source, follow these steps.

### 3.1. Clone the Repository

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

### 3.2. Install Environment
We provide a shell script to automate the setup of Conda environments (`bear-hub` and `bactopia`).

```bash
chmod +x install_bear.sh
./install_bear.sh
```

### 3.3. Run the Application
Use the launcher script to start the interface.

```bash
chmod +x run_bear.sh
./run_bear.sh
```
This will activate the `bear-hub` environment and launch Streamlit.

---

## 4. Building Executables Locally

If you want to build the AppImage yourself (e.g., for development), you can use the provided GitHub Actions workflow or run PyInstaller locally.

**Requirements:** `pyinstaller`, `appimagetool`

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# 2. Build binaries
pyinstaller --onefile --clean --name bear-installer bear_installer.py

pyinstaller --onefile --clean \
    --name bear-hub \
    --add-data "BEAR-HUB.py:." \
    --add-data "utils.py:." \
    --add-data "pages:pages" \
    --add-data "static:static" \
    --collect-all streamlit \
    --collect-all altair \
    --collect-all pandas \
    --collect-all pyyaml \
    bear_launcher.py

# 3. Create AppImage (requires AppDir structure and appimagetool)
# See .github/workflows/build_executables.yml for the full steps.
```

---

## 5. Usage & Navigation

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

## License & Disclaimer

**License**: MIT License.

**Disclaimer**:
> **BEAR-HUB** is an unofficial interface for **Bactopia** (https://github.com/bactopia).
> Bactopia is developed and maintained by its original authors. We have no official affiliation with the Bactopia project.
> All credit for the underlying analysis pipelines goes to the Bactopia team.

---

*Developed by João Pedro Stepan Wagner.*
