#!/usr/bin/env python3
"""
BEAR-HUB Installer
==================

This script sets up the environment for BEAR-HUB.
It checks for necessary dependencies (Docker, Conda) and sets up the
'bactopia' environment required for the pipelines.

It replaces the legacy 'install_bear.sh'.
"""

import os
import shutil
import subprocess
import sys
import platform
import json

# Configuration
APP_NAME = "BEAR-HUB"
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if getattr(sys, 'frozen', False):
    # If running as a PyInstaller bundle, we might want the directory of the executable
    ROOT_DIR = os.path.dirname(sys.executable)

DATA_DIR = os.path.join(ROOT_DIR, "data")
OUT_DIR = os.path.join(ROOT_DIR, "bactopia_out")
CONFIG_FILE = os.path.join(ROOT_DIR, ".bear-hub.env")

def print_header():
    print("===============================")
    print(f"  {APP_NAME} - Installer")
    print("  (local mode, Bactopia via Docker)")
    print("===============================")
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"OUT_DIR : {OUT_DIR}")
    print()

def check_command(command):
    """Checks if a command exists in the PATH."""
    return shutil.which(command)

def get_conda_bin():
    """Finds conda or mamba binary."""
    mamba = check_command("mamba")
    conda = check_command("conda")

    # We return a tuple: (binary_to_use, is_mamba)
    if mamba:
        print("\nUsing 'mamba' for environment creation.")
        return mamba, True
    if conda:
        return conda, False
    return None, False

def get_env_prefix(conda_bin, env_name):
    """
    Gets the prefix path of a conda environment by name.
    Uses 'conda env list --json' for more reliability if possible,
    parsing standard output otherwise.
    """
    # Try JSON output first (more reliable)
    try:
        # We assume conda_bin supports 'env list --json'
        # Some older versions might not, or if it is mamba/micromamba.
        # But 'conda env list --json' is standard.
        # However, if conda_bin is mamba, it might be slightly different, but usually compatible.

        # We use the base 'conda' command for listing if available because mamba can be slow or verbose
        list_bin = check_command("conda") or conda_bin

        result = subprocess.run(
            [list_bin, "env", "list", "--json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)

        # data['envs'] is a list of paths.
        # We need to find the one ending with env_name.
        # NOTE: This is slightly risky if multiple envs have same name in different paths,
        # but standard conda/mamba setup usually works this way.

        # A safer approach used in the bash script was filtering by name in the first column.
        # JSON output just gives paths.

        for path in data.get("envs", []):
            if os.path.basename(path) == env_name:
                return path
    except Exception:
        # Fallback to text parsing if JSON fails
        pass

    # Fallback text parsing
    try:
        list_bin = check_command("conda") or conda_bin
        result = subprocess.run(
            [list_bin, "env", "list"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if line.startswith("#"): continue
            parts = line.split()
            if len(parts) >= 2 and parts[0] == env_name:
                # The last part is usually the path
                return parts[-1]
    except Exception:
        pass

    return None

def create_bactopia_env(conda_bin, is_mamba):
    """Creates the bactopia environment."""
    print("\nVerifying environment 'bactopia'...")

    prefix = get_env_prefix(conda_bin, "bactopia")

    if prefix:
        print(f"Environment 'bactopia' already exists at: {prefix}")
        return prefix

    print("Creating environment 'bactopia' with Bactopia...")
    print("  (The pipeline will run with '-profile docker' by BEAR-HUB)")

    channels = ["conda-forge", "bioconda"]
    cmd = [conda_bin, "create", "-y", "-n", "bactopia"]
    for c in channels:
        cmd.extend(["-c", c])
    cmd.append("bactopia")

    subprocess.check_call(cmd)

    prefix = get_env_prefix(conda_bin, "bactopia")
    if prefix:
        print(f"Environment 'bactopia' created at: {prefix}")
    else:
        print("WARNING: 'bactopia' environment created but prefix could not be determined.")

    return prefix

def ensure_nextflow(prefix, conda_bin, is_mamba):
    """Ensures nextflow is installed in the environment."""
    print("\nLocating final prefix for 'bactopia' environment...")

    if not prefix:
        print("ERROR: Could not find prefix for 'bactopia'.")
        sys.exit(1)

    nf_path = os.path.join(prefix, "bin", "nextflow")

    if os.path.exists(nf_path) and os.access(nf_path, os.X_OK):
        print(f"nextflow found at: {nf_path}")
        return

    print(f"\nnextflow not found at '{nf_path}'.")
    print("Attempting to install nextflow inside 'bactopia' environment...")

    cmd = [conda_bin, "install", "-y", "-n", "bactopia", "-c", "bioconda", "-c", "conda-forge", "nextflow"]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("Conda install of nextflow failed. Trying direct download...")

    if os.path.exists(nf_path) and os.access(nf_path, os.X_OK):
        print(f"nextflow installed at: {nf_path}")
        return

    # Fallback: Download binary
    print("\nDownloading nextflow via official script (get.nextflow.io)...")
    bin_dir = os.path.join(prefix, "bin")
    os.makedirs(bin_dir, exist_ok=True)

    # Try curl
    if check_command("curl"):
        # Pipe to bash to run the installer script, which downloads the binary into CWD
        subprocess.call(f"cd \"{bin_dir}\" && curl -fsSL https://get.nextflow.io | bash", shell=True)
    elif check_command("wget"):
        subprocess.call(f"cd \"{bin_dir}\" && wget -qO- https://get.nextflow.io | bash", shell=True)
    else:
        print("ERROR: Neither curl nor wget found. Cannot download nextflow.")
        sys.exit(1)

    os.chmod(os.path.join(bin_dir, "nextflow"), 0o755)

    if os.path.exists(nf_path) and os.access(nf_path, os.X_OK):
        print(f"nextflow installed at: {nf_path}")
    else:
        print("ERROR: Failed to ensure a usable 'nextflow'.")
        sys.exit(1)

def main():
    print_header()

    # Create directories
    os.makedirs(ROOT_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # Check Docker
    docker_bin = check_command("docker")
    if not docker_bin:
        print("\nERROR: 'docker' not found in PATH.")
        print("BEAR-HUB requires Docker to run Bactopia.")
        print("Please install Docker and try again.")
        sys.exit(1)
    else:
        print(f"\nDocker found at: {docker_bin}")

    # Check Conda/Mamba
    conda_bin, is_mamba = get_conda_bin()
    if not conda_bin:
        print("\nERROR: Neither 'mamba' nor 'conda' found in PATH.")
        print("BEAR-HUB requires Conda or Mamba to manage bioinformatics environments.")
        sys.exit(1)

    # Create Bactopia Env
    prefix = create_bactopia_env(conda_bin, is_mamba)

    # Ensure Nextflow
    ensure_nextflow(prefix, conda_bin, is_mamba)

    # Write Config
    print(f"\nNXF_CONDA_EXE will use: {conda_bin}")

    with open(CONFIG_FILE, "w") as f:
        f.write("# Generated by BEAR-HUB Installer\n")
        f.write(f"export BEAR_HUB_ROOT=\"{ROOT_DIR}\"\n")
        f.write(f"export BEAR_HUB_BASEDIR=\"{DATA_DIR}\"\n")
        f.write(f"export BEAR_HUB_OUTDIR=\"{OUT_DIR}\"\n")
        f.write(f"export BEAR_HUB_DATA=\"{DATA_DIR}\"\n")
        f.write("\n# Environment for Nextflow/Bactopia\n")
        f.write(f"export BACTOPIA_ENV_PREFIX=\"{prefix}\"\n")
        f.write(f"export NXF_CONDA_EXE=\"{conda_bin}\"\n")

    print(f"\nConfig saved to: {CONFIG_FILE}")
    print("\nInstallation complete.")
    print("You can now launch the application using the 'bear-hub' executable.")

if __name__ == "__main__":
    main()
