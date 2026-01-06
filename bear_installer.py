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
import traceback
import datetime
import re

# Configuration
APP_NAME = "BEAR-HUB"

def get_root_dir():
    # Allow override via environment variable (for testing)
    env_root = os.environ.get("BEAR_HUB_ROOT")
    if env_root:
        return os.path.abspath(env_root)

    if getattr(sys, 'frozen', False):
        # AppImage/Frozen: Use user home directory to ensure we can write files
        # The executable is inside a read-only SquashFS mount
        return os.path.join(os.path.expanduser("~"), "BEAR-HUB")
    else:
        # Dev/Script: Use local directory
        return os.path.abspath(os.path.dirname(__file__))

ROOT_DIR = get_root_dir()
DATA_DIR = os.path.join(ROOT_DIR, "data")
OUT_DIR = os.path.join(ROOT_DIR, "bactopia_out")
CONFIG_FILE = os.path.join(ROOT_DIR, ".bear-hub.env")
LOG_FILE = os.path.join(ROOT_DIR, "install.log")

class TeeLogger:
    """Writes to both stdout/stderr and a log file."""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush() # Ensure it's written immediately

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def setup_logging():
    os.makedirs(ROOT_DIR, exist_ok=True)
    sys.stdout = TeeLogger(LOG_FILE)
    sys.stderr = sys.stdout # Redirect stderr to same log
    print(f"--- Installer started at {datetime.datetime.now()} ---")

def print_header():
    print("===============================")
    print(f"  {APP_NAME} - Installer")
    print("  (local mode, Bactopia via Docker)")
    print("===============================")
    print(f"ROOT_DIR: {ROOT_DIR}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"OUT_DIR : {OUT_DIR}")
    print(f"LOG_FILE: {LOG_FILE}")
    print()

def check_command(command):
    """Checks if a command exists in the PATH."""
    return shutil.which(command)

def install_docker_if_missing():
    """Attempts to install docker on Debian/Ubuntu systems."""
    if not check_command("apt-get"):
        return False

    print("Attempting to install Docker via apt-get (requires sudo)...")
    try:
        subprocess.check_call(["sudo", "apt-get", "update"])
        subprocess.check_call(["sudo", "apt-get", "install", "-y", "docker.io"])
        return True
    except Exception as e:
        print(f"Docker installation failed: {e}")
        return False

def get_conda_bin():
    """Finds conda or mamba binary."""
    # 1. Check PATH
    mamba = check_command("mamba")
    if mamba:
        print("\nUsing 'mamba' for environment creation.")
        return mamba, True

    conda = check_command("conda")
    if conda:
        return conda, False

    # 2. Check common locations (vital for GUI launches where PATH might be minimal)
    print("\n'conda'/'mamba' not found in PATH. Checking common locations...")
    home = os.path.expanduser("~")
    common_paths = [
        os.path.join(home, "miniconda3", "bin", "conda"),
        os.path.join(home, "anaconda3", "bin", "conda"),
        os.path.join(home, "miniforge3", "bin", "mamba"),
        os.path.join(home, "mambaforge", "bin", "mamba"),
        "/opt/conda/bin/conda"
    ]
    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            print(f"Found binary at: {path}")
            return path, path.endswith("mamba")

    return None, False

def get_env_prefix(conda_bin, env_name):
    """
    Gets the prefix path of a conda environment by name.
    Uses 'conda env list --json' for more reliability if possible,
    parsing standard output otherwise.
    """
    # Try JSON output first (more reliable)
    try:
        # We use the base 'conda' command for listing if available because mamba can be slow or verbose
        # If we found mamba directly, we use it.
        list_bin = check_command("conda") or conda_bin

        result = subprocess.run(
            [list_bin, "env", "list", "--json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)

        for path in data.get("envs", []):
            if os.path.basename(path) == env_name:
                return path
    except Exception:
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
                return parts[-1]
    except Exception:
        pass

    return None

def create_bear_hub_env(conda_bin):
    """Creates the bear-hub environment for the UI."""
    print("\nVerifying environment 'bear-hub'...")

    prefix = get_env_prefix(conda_bin, "bear-hub")

    if prefix:
        print(f"Environment 'bear-hub' already exists at: {prefix}")
        return prefix

    print("Creating environment 'bear-hub' (Python 3.11, Streamlit, PyYAML)...")

    cmd = [conda_bin, "create", "-y", "-n", "bear-hub", "-c", "conda-forge",
           "python=3.11", "streamlit", "pyyaml"]

    subprocess.check_call(cmd)

    prefix = get_env_prefix(conda_bin, "bear-hub")
    if prefix:
        print(f"Environment 'bear-hub' created at: {prefix}")
    else:
        print("WARNING: 'bear-hub' environment created but prefix could not be determined.")

    return prefix

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

# ================= Java Handling =================

def get_java_version(java_bin):
    """Returns the major version of Java or 0 if not found/parseable."""
    try:
        # java -version prints to stderr
        res = subprocess.run([java_bin, "-version"], capture_output=True, text=True)
        # Output example: openjdk version "17.0.9" ...
        output = res.stderr + "\n" + res.stdout

        # Match version "1.8... or version "17...
        match = re.search(r'version "(\d+)', output)
        if match:
            v = int(match.group(1))
            if v == 1: # Handle 1.8 etc
                match = re.search(r'version "1\.(\d+)', output)
                if match:
                    return int(match.group(1))
            return v
        return 0
    except Exception:
        return 0

def find_java(env_prefix):
    """
    Checks for Java in the env prefix first, then system.
    Returns (path_to_java, version_int, is_system_fallback).
    """
    min_java = 17

    # 1. Check Env
    if env_prefix:
        env_java = os.path.join(env_prefix, "bin", "java")
        if os.path.exists(env_java) and os.access(env_java, os.X_OK):
            v = get_java_version(env_java)
            if v >= min_java:
                return env_java, v, False
            else:
                print(f"Java found in env but too old: version {v} (required >= {min_java})")

    # 2. Check System
    sys_java = shutil.which("java")
    if sys_java:
        v = get_java_version(sys_java)
        if v >= min_java:
            return sys_java, v, True
        else:
            print(f"System Java found but too old: version {v} (required >= {min_java})")

    return None, 0, False

def install_java(conda_bin, env_name="bactopia"):
    """Installs OpenJDK 17 into the specified environment."""
    print(f"\nInstalling OpenJDK 17 into '{env_name}' environment...")
    cmd = [conda_bin, "install", "-n", env_name, "-c", "conda-forge", "openjdk=17", "-y"]
    subprocess.check_call(cmd)

# =================================================

def ensure_nextflow(prefix, conda_bin, is_mamba, java_home=None):
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

    # Prepare environment for the curl command (needs JAVA)
    env_copy = os.environ.copy()
    if java_home:
        print(f"Using JAVA_HOME={java_home} for installation...")
        env_copy["JAVA_HOME"] = java_home
        # Prepend to PATH just in case
        env_copy["PATH"] = os.path.join(java_home, "bin") + os.pathsep + env_copy["PATH"]

    # Try curl
    dl_cmd = None
    if check_command("curl"):
        dl_cmd = f"cd \"{bin_dir}\" && curl -fsSL https://get.nextflow.io | bash"
    elif check_command("wget"):
        dl_cmd = f"cd \"{bin_dir}\" && wget -qO- https://get.nextflow.io | bash"
    else:
        print("ERROR: Neither curl nor wget found. Cannot download nextflow.")
        sys.exit(1)

    subprocess.call(dl_cmd, shell=True, env=env_copy)
    os.chmod(os.path.join(bin_dir, "nextflow"), 0o755)

    if os.path.exists(nf_path) and os.access(nf_path, os.X_OK):
        print(f"nextflow installed at: {nf_path}")
    else:
        print("ERROR: Failed to ensure a usable 'nextflow'.")
        sys.exit(1)

def deploy_streamlit_config():
    """
    Deploys the bundled .streamlit/config.toml to the installation directory.
    Also ensures credentials.toml exists to suppress email prompt.
    """
    # 1. Determine Source Directory (Frozen vs Script)
    if getattr(sys, 'frozen', False):
        source_base = sys._MEIPASS
    else:
        source_base = os.path.dirname(os.path.abspath(__file__))

    source_config = os.path.join(source_base, ".streamlit", "config.toml")

    # 2. Determine Target Directory (ROOT_DIR/.streamlit)
    target_dir = os.path.join(ROOT_DIR, ".streamlit")
    os.makedirs(target_dir, exist_ok=True)
    target_config = os.path.join(target_dir, "config.toml")

    # 3. Copy config.toml
    if os.path.exists(source_config):
        print(f"\nDeploying Streamlit config to {target_config}...")
        try:
            shutil.copy2(source_config, target_config)
        except Exception as e:
            print(f"WARNING: Failed to copy config.toml: {e}")
    else:
        print(f"\nWARNING: Source config not found at {source_config}. Skipping deployment.")

    # 4. Create credentials.toml to suppress email prompt
    # We still check ~/.streamlit for credentials as that is global,
    # but we can also put it in the local dir if we set STREAMLIT_CONFIG_FILE?
    # Actually, credentials are usually global. Let's stick to the existing logic
    # for credentials but put them in the global home dir as Streamlit expects them there
    # unless we override everything.
    # However, to be safe and consistent with previous logic, let's keep the ~/.streamlit check for credentials.

    home = os.path.expanduser("~")
    global_st_dir = os.path.join(home, ".streamlit")
    os.makedirs(global_st_dir, exist_ok=True)

    creds_file = os.path.join(global_st_dir, "credentials.toml")
    if not os.path.exists(creds_file):
        print(f"Creating {creds_file} to suppress email prompt...")
        with open(creds_file, "w") as f:
            f.write('[general]\nemail = ""\n')

def main():
    setup_logging()
    print_header()

    # Create directories
    os.makedirs(ROOT_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # Check Docker
    docker_bin = check_command("docker")
    if not docker_bin:
        print("\n'docker' not found in PATH.")
        if install_docker_if_missing():
            docker_bin = check_command("docker")

        if not docker_bin:
            print("\nERROR: 'docker' not found and automatic installation failed.")
            print("BEAR-HUB requires Docker to run Bactopia.")
            print("Please install Docker manually (e.g. 'sudo apt install docker.io') and try again.")
            sys.exit(1)
        else:
            print(f"Docker installed successfully at: {docker_bin}")
    else:
        print(f"\nDocker found at: {docker_bin}")

    # Check Conda/Mamba
    conda_bin, is_mamba = get_conda_bin()
    if not conda_bin:
        print("\nERROR: Neither 'mamba' nor 'conda' found.")
        print("BEAR-HUB requires Conda or Mamba to manage bioinformatics environments.")
        sys.exit(1)

    # Create Environments
    create_bear_hub_env(conda_bin)
    prefix = create_bactopia_env(conda_bin, is_mamba)

    # --- Java Check & Install ---
    print("\nChecking for Java (required for Nextflow)...")
    java_bin, java_ver, is_sys = find_java(prefix)

    if not java_bin:
        print("Java not found or too old (<17).")
        try:
            install_java(conda_bin, "bactopia")
            # Re-check
            java_bin, java_ver, is_sys = find_java(prefix)
            if not java_bin:
                print("ERROR: Failed to install Java. Please install OpenJDK 17+ manually.")
                sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to install Java: {e}")
            sys.exit(1)

    print(f"Using Java: {java_bin} (Version {java_ver})")

    # Determine JAVA_HOME
    # For standard Linux java/openjdk, binary is often in bin/java, so home is parent/parent
    # e.g. /usr/lib/jvm/java-17/bin/java -> /usr/lib/jvm/java-17
    # For conda: prefix/bin/java -> prefix is technically the conda env root, but standard JAVA_HOME logic usually expects bin/..
    # So dirname(dirname(java_bin)) is safe.
    final_java_home = os.path.dirname(os.path.dirname(java_bin))

    # Ensure Nextflow (passing java_home if needed for the install script)
    ensure_nextflow(prefix, conda_bin, is_mamba, java_home=final_java_home)

    # Deploy Streamlit Config
    deploy_streamlit_config()

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
        f.write(f"export JAVA_HOME=\"{final_java_home}\"\n")
        # Also ensure PATH includes Java
        f.write(f"export PATH=\"{final_java_home}/bin:$PATH\"\n")

    print(f"\nConfig saved to: {CONFIG_FILE}")
    print("\nInstallation complete.")
    print("You can now launch the application using the 'bear-hub' executable.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Pause so user can read the terminal output if launched via GUI
        # Even with AppRun pause, this double pause is harmless and safe
        print("\n")

        # Check for non-interactive mode
        non_interactive = os.environ.get("BEAR_NONINTERACTIVE") == "1"

        if not non_interactive:
            try:
                input("Press Enter to close this window...")
            except:
                pass