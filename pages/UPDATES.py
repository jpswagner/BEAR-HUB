# pages/UPDATES.py
# ---------------------------------------------------------------------
# System Updates & Status Page
# ---------------------------------------------------------------------

import streamlit as st
import subprocess
import os
import sys
import shutil
import utils
import requests
import pathlib
import re

# ============================= Configuration =============================

st.set_page_config(page_title="System Status - BEAR-HUB", page_icon="🔄", layout="wide")

# Ensure environment variables are loaded
utils.bootstrap_bear_env_from_file()

# --- Command Constants ---

# For Bactopia, we need to run inside its conda environment.
# We try to detect the environment name or prefix.
BACTOPIA_ENV_NAME = "bactopia" # Default name created by install_bear.sh

def _get_conda_run_cmd(cmd_list, env_name=BACTOPIA_ENV_NAME):
    """
    Wraps a command to run inside a conda environment.
    Tries 'mamba' then 'conda'.
    """
    # join cmd_list if it is a list
    if isinstance(cmd_list, list):
        cmd_str = " ".join(cmd_list)
    else:
        cmd_str = cmd_list

    runner = shutil.which("mamba") or shutil.which("conda")
    if not runner:
        return cmd_str # Fallback: return string for consistency

    return f"{runner} run -n {env_name} {cmd_str}"

CMD_BACTOPIA_VERSION = _get_conda_run_cmd(["bactopia", "--version"])
CMD_NEXTFLOW_VERSION = "nextflow -version"
CMD_DOCKER_VERSION = "docker --version"

# ============================= Helper Functions =============================

def get_command_output(cmd, shell=False):
    """
    Runs a command and returns its stdout.
    Returns 'Not installed / Not found' on failure.
    """
    try:
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()

        output = subprocess.check_output(cmd, shell=shell, stderr=subprocess.STDOUT, text=True)
        return output.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Not installed / Not found"
    except Exception as e:
        # In case of other errors (like command not found in shell=True)
        return "Not installed / Not found"

def get_local_app_version():
    """
    Reads the local version from the VERSION file in the root directory.
    Returns the version string (e.g., 'v1.0.0') or 'Unknown'.
    """
    try:
        # Assuming VERSION is in the root of the repo (parent of pages/)
        # Or if running from root, just 'VERSION'.
        # We try to locate it relative to this file.
        root = pathlib.Path(__file__).resolve().parent.parent
        version_file = root / "VERSION"

        if version_file.exists():
            return version_file.read_text().strip()

        # Fallback: check CWD
        cwd_version = pathlib.Path("VERSION")
        if cwd_version.exists():
             return cwd_version.read_text().strip()

    except Exception:
        pass
    return "Unknown"


def get_latest_github_release(repo="jpswagner/BEAR-HUB", include_prerelease=True):
    """
    Fetch the latest release tag from GitHub.
    - First tries /releases/latest (stable only).
    - If none exist and include_prerelease is True, falls back to /releases.
    Returns (tag_name, html_url) or (None, None) on failure.
    """
    base = f"https://api.github.com/repos/{repo}"

    # 1) Try stable latest
    try:
        resp = requests.get(f"{base}/releases/latest", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tag_name"), data.get("html_url")
    except Exception:
        # ignore and fall through to prerelease logic
        pass

    if not include_prerelease:
        return None, None

    # 2) Fallback: look at the full releases list (includes pre-releases)
    try:
        resp = requests.get(f"{base}/releases", timeout=3)
        if resp.status_code == 200:
            releases = resp.json()
            # releases is a list, newest first
            for rel in releases:
                if rel.get("draft"):
                    continue  # skip drafts
                # If we got here, accept both prerelease and normal
                return rel.get("tag_name"), rel.get("html_url")
    except Exception:
        pass

    return None, None


def clean_bactopia_version(raw_output):
    """Cleans up the bactopia version string."""
    if "Not installed" in raw_output:
        return raw_output
    # Usually output is like "bactopia 3.0.0" or similar.
    # We just return it as is if it looks reasonable,
    # but strip extra newlines if any.
    return raw_output.splitlines()[0] if raw_output else "Unknown"

def clean_nextflow_version(raw_output):
    """Parses Nextflow output to find the version line."""
    if "Not installed" in raw_output:
        return raw_output

    # Look for a line containing "version"
    # Example: "nextflow version 23.10.0.5889"
    for line in raw_output.splitlines():
        if "version" in line.lower():
            return line.strip()

    # Fallback
    lines = raw_output.strip().splitlines()
    return lines[0] if lines else "Unknown"

def get_java_info():
    """
    Detects Java version.
    Checks JAVA_HOME, then bactopia env, then system PATH.
    """
    # 1. Check JAVA_HOME
    jh = os.environ.get("JAVA_HOME")
    if jh:
        bin_path = os.path.join(jh, "bin", "java")
        if os.path.exists(bin_path):
            return get_command_output(f"{bin_path} -version", shell=True)

    # 2. Check Bactopia Env
    bact_env = os.environ.get("BACTOPIA_ENV_PREFIX")
    if bact_env:
        bin_path = os.path.join(bact_env, "bin", "java")
        if os.path.exists(bin_path):
            return get_command_output(f"{bin_path} -version", shell=True)

    # 3. Check PATH
    return get_command_output("java -version", shell=True)

def clean_java_version(raw_output):
    """Parses java -version output."""
    if "Not installed" in raw_output:
        return raw_output

    # Output is usually on stderr, but get_command_output merges it.
    # "openjdk version "17.0.9" ..."
    for line in raw_output.splitlines():
        if "version" in line:
            return line.strip()

    return raw_output.splitlines()[0] if raw_output else "Unknown"


# ============================= UI Layout =============================

st.title("🔄 System Status & Versions")
st.markdown("View BEAR-HUB and external tool versions. Updates must be installed manually.")

st.divider()

# --- Section: Versions ---
col1, col2 = st.columns(2)

with col1:
    st.header("BEAR-HUB")

    # 1. Local Version
    local_version = get_local_app_version()
    st.write(f"**Current Version:** `{local_version}`")

    # 2. Remote Check
    latest_tag, release_url = get_latest_github_release()

    if latest_tag:
        if local_version == latest_tag:
            st.success(f"You are using the latest version ({local_version}). ✅")
        else:
            # We assume if tags differ, remote is likely newer or at least different.
            # Simple string comparison isn't perfect for semantic versioning but usually sufficient if format is consistent.
            st.warning(f"**New version available:** `{latest_tag}` (you have `{local_version}`)")
            st.info(f"A newer BEAR-HUB version is available. Download the latest release (e.g. AppImage) from the GitHub Releases page and replace your current file.")
            st.markdown(f"👉 [**Go to GitHub Releases**]({release_url})")
    else:
        st.write("Could not check for new releases (offline or GitHub unavailable).")


with col2:
    st.header("External Tools")

    # Bactopia
    raw_bactopia = get_command_output(CMD_BACTOPIA_VERSION, shell=True)
    bactopia_v = clean_bactopia_version(raw_bactopia)
    st.text_input("Bactopia Version", value=bactopia_v, disabled=True)

    # Nextflow
    # Check if we should use the one from bactopia env or system
    nf_v_raw = get_command_output(CMD_NEXTFLOW_VERSION, shell=True)
    if "Not installed" in nf_v_raw:
        # Try finding it via utils
        nf_bin = utils.get_nextflow_bin()
        if nf_bin and nf_bin != "nextflow":
             nf_v_raw = get_command_output(f"{nf_bin} -version", shell=True)

    nf_display = clean_nextflow_version(nf_v_raw)
    st.text_input("Nextflow Version", value=nf_display, disabled=True)

    # Java
    raw_java = get_java_info()
    java_display = clean_java_version(raw_java)
    st.text_input("Java Version", value=java_display, disabled=True)

    # Docker
    docker_v = get_command_output(CMD_DOCKER_VERSION, shell=True)
    # Docker version output can be verbose, take first line
    docker_display = docker_v.splitlines()[0] if docker_v and "Not installed" not in docker_v else docker_v
    st.text_input("Docker Version", value=docker_display, disabled=True)
