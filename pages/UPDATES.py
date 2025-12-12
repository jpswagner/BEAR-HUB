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
import json

# ============================= Configuration =============================

st.set_page_config(page_title="Updates - BEAR-HUB", page_icon="🔄", layout="wide")

# Ensure environment variables are loaded
utils.bootstrap_bear_env_from_file()

# --- Command Constants ---
# Centralized commands for easier adaptation.

def get_git_pull_cmd():
    """Returns a robust git pull command using the current branch."""
    try:
        # Get current branch
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if branch and branch != "HEAD":
            # Explicitly pull origin <branch>
            return f"git pull origin {branch}"
    except Exception:
        pass
    return "git pull"

CMD_GIT_PULL = get_git_pull_cmd()
CMD_PIP_INSTALL = f"{sys.executable} -m pip install -r requirements.txt"

# Check if running in frozen mode (AppImage)
IS_FROZEN = getattr(sys, "frozen", False)

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
CMD_NEXTFLOW_VERSION = "nextflow -version" # Nextflow might be in PATH or BACTOPIA env
CMD_DOCKER_VERSION = "docker --version"

# Update commands
CMD_UPDATE_BACTOPIA_ENV = ""
if shutil.which("mamba"):
    CMD_UPDATE_BACTOPIA_ENV = f"mamba update -n {BACTOPIA_ENV_NAME} --all -y"
elif shutil.which("conda"):
    CMD_UPDATE_BACTOPIA_ENV = f"conda update -n {BACTOPIA_ENV_NAME} --all -y"
else:
    CMD_UPDATE_BACTOPIA_ENV = "echo 'Error: mamba/conda not found'"

# ============================= Helper Functions =============================

def get_command_output(cmd, shell=False):
    """
    Runs a command and returns its stdout.
    Returns 'Not installed / Error' on failure.
    """
    try:
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()

        output = subprocess.check_output(cmd, shell=shell, stderr=subprocess.STDOUT, text=True)
        return output.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "Not installed / Not found"
    except Exception as e:
        return f"Error: {str(e)}"

def get_git_info():
    """Returns a tuple (branch, commit_hash, status_summary)."""
    try:
        # Branch
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
        # Commit
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        # Status
        status_out = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        dirty = " (Dirty)" if status_out else " (Clean)"
        return branch, commit, dirty
    except Exception:
        return "Unknown", "Unknown", ""

def get_latest_github_release(repo="jpswagner/BEAR-HUB"):
    """
    Fetches the latest release tag from GitHub API.
    Returns (tag_name, html_url) or ("Unknown", link).
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tag_name", "Unknown"), data.get("html_url", f"https://github.com/{repo}/releases")
    except Exception:
        pass
    return "Unknown", f"https://github.com/{repo}/releases"

# ============================= UI Layout =============================

st.title("🔄 System Updates")
st.markdown("Check current versions and update the application and dependencies.")

st.divider()

# --- Section 1: System Status ---
st.header("1. System Status")

col1, col2 = st.columns(2)

with col1:
    st.subheader("BEAR-HUB (App)")

    if IS_FROZEN:
        st.info("**Mode:** AppImage (Frozen)")

        # Check for updates
        latest_tag, release_url = get_latest_github_release()
        if latest_tag != "Unknown":
            st.metric("Latest GitHub Release", latest_tag)
        else:
            st.write("Could not fetch latest release info from GitHub.")

        st.markdown(f"👉 [View Releases on GitHub]({release_url})")

        git_available = False
    else:
        # Get Git Info
        branch, commit, dirty = get_git_info()
        if branch == "Unknown":
             st.warning("Git repository not detected. Updates via Git are disabled.")
             git_available = False
        else:
             st.success(f"**Branch:** `{branch}`\n\n**Commit:** `{commit}`{dirty}")
             git_available = True

    # App Version (if defined in a file, otherwise using git info is fine)
    # st.write(f"**App Version:** {APP_VERSION}")

with col2:
    st.subheader("External Tools")

    # Bactopia
    bactopia_v = get_command_output(CMD_BACTOPIA_VERSION, shell=True)
    st.text_input("Bactopia Version", value=bactopia_v, disabled=True)

    # Nextflow
    # Check if we should use the one from bactopia env or system
    # We will try system first, then custom logic
    nf_v = get_command_output(CMD_NEXTFLOW_VERSION, shell=True)
    # If not found in path, try looking in BACTOPIA_ENV_PREFIX if set
    if "Not installed" in nf_v:
        # Try finding it via utils
        nf_bin = utils.get_nextflow_bin()
        if nf_bin and nf_bin != "nextflow":
             nf_v = get_command_output(f"{nf_bin} -version", shell=True)

    # Parse Nextflow version - look for line with 'version'
    nf_display = "Unknown"
    for line in nf_v.splitlines():
        if "version" in line.lower():
            nf_display = line.strip()
            break
    if nf_display == "Unknown" and nf_v.strip():
        # Fallback to first non-empty line
        nf_display = nf_v.strip().splitlines()[0]

    st.text_input("Nextflow Version", value=nf_display, disabled=True)

    # Docker
    docker_v = get_command_output(CMD_DOCKER_VERSION, shell=True)
    st.text_input("Docker Version", value=docker_v, disabled=True)


st.divider()

# --- Section 2: Updates ---
st.header("2. Run Updates")
st.warning("⚠️ **Warning:** Only run updates if you have appropriate system permissions. Updates may modify files and environments.")

u_col1, u_col2, u_col3 = st.columns(3)

# Namespace for logs
NS_UPDATES = "updates_runner"

# --- Button 1: Git Pull ---
with u_col1:
    st.markdown("### Update App Code")
    if IS_FROZEN:
        st.info("To update the AppImage, please download the latest release.")
    else:
        st.caption("Runs `git pull` to fetch the latest code from GitHub.")
        if st.button("Update BEAR-HUB (Git Only)", disabled=not git_available, use_container_width=True):
            if not git_available:
                st.error("Git not found.")
            else:
                utils.start_async_runner_ns(CMD_GIT_PULL, NS_UPDATES)

# --- Button 2: Full Update ---
with u_col2:
    st.markdown("### Full App Update")
    if IS_FROZEN:
        st.write("Dependencies are bundled in the AppImage.")
    else:
        st.caption("Runs `git pull` AND installs dependencies (`pip install`).")
        if st.button("Update BEAR-HUB (Full)", disabled=not git_available, use_container_width=True):
             if not git_available:
                st.error("Git not found.")
             else:
                # Chain commands
                full_cmd = f"{CMD_GIT_PULL} && {CMD_PIP_INSTALL}"
                utils.start_async_runner_ns(full_cmd, NS_UPDATES)

# --- Button 3: Bactopia Env ---
with u_col3:
    st.markdown("### Update Bactopia Env")
    st.caption("Updates the `bactopia` conda environment.")
    if st.button("Update Bactopia Env", use_container_width=True):
        utils.start_async_runner_ns(CMD_UPDATE_BACTOPIA_ENV, NS_UPDATES)


# --- Log Output ---
st.markdown("### Update Log")

# Render log box
utils.render_log_box_ns(NS_UPDATES, height=400)

# Check status and update UI
if st.session_state.get(f"{NS_UPDATES}_running"):
    # Drain queue
    utils.drain_log_queue_ns(NS_UPDATES)

    # Stop button
    if st.button("Stop", key="stop_updates"):
        utils.request_stop_ns(NS_UPDATES)

    # Check if finished
    status_box = st.empty()
    if utils.check_status_and_finalize_ns(NS_UPDATES, status_box):
        st.success("Process finished. Please restart the application if code was updated.")
        if st.button("Refresh Page"):
            st.rerun()

    # Auto-refresh to keep streaming
    time_sleep = 0.5
    import time
    time.sleep(time_sleep)
    st.rerun()

else:
    # If not running, maybe it just finished or hasn't started
    pass
