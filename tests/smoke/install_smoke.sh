#!/bin/bash
set -euo pipefail

# Smoke Test Harness for BEAR-HUB Installer
# Intended to run inside a clean Docker container

echo "==========================================="
echo "   BEAR-HUB Smoke Test Harness"
echo "==========================================="

# Ensure we are in the repo root or can find the installer
# Assuming script is run from repo root (mounted at /app or similar)
REPO_ROOT="$(pwd)"
INSTALLER_SCRIPT="${REPO_ROOT}/bear_installer.py"

if [ ! -f "$INSTALLER_SCRIPT" ]; then
    echo "ERROR: Installer script not found at $INSTALLER_SCRIPT"
    exit 1
fi

# Define artifacts dir
ARTIFACTS_DIR="${REPO_ROOT}/artifacts"
mkdir -p "$ARTIFACTS_DIR"

# Install Miniforge (Mamba) if not present
# The installer requires conda/mamba.
# The Dockerfile is "clean", so we must bootstrap this prerequisite.
if ! command -v conda &> /dev/null && ! command -v mamba &> /dev/null; then
    echo ">>> Bootstrapping Miniforge (Mamba)..."
    curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
    bash Miniforge3-$(uname)-$(uname -m).sh -b -p "${HOME}/miniforge3"
    rm Miniforge3-$(uname)-$(uname -m).sh

    # Initialize for this shell
    eval "$("${HOME}/miniforge3/bin/conda" shell.bash hook)"
    export PATH="${HOME}/miniforge3/bin:$PATH"

    echo ">>> Mamba installed."
    mamba --version
else
    echo ">>> Conda/Mamba already present."
fi

# Set Environment Variables for CI
export BEAR_NONINTERACTIVE=1
# Install to a specific directory in the container
export BEAR_HUB_ROOT="${HOME}/BEAR-HUB-TEST"
# Log file location (installer writes to install.log in ROOT, we'll move it later)

echo ">>> Running bear_installer.py..."
# We run with python3. Ensure python3 is available (should be from Miniforge or system)
python3 "$INSTALLER_SCRIPT"

# Verify Installation
echo ">>> Verifying Installation..."

CONFIG_FILE="${BEAR_HUB_ROOT}/.bear-hub.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "FAIL: Config file not found at $CONFIG_FILE"
    exit 1
fi

echo ">>> Sourcing $CONFIG_FILE..."
source "$CONFIG_FILE"

FAILED=0

check_cmd() {
    local cmd="$1"
    local name="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "PASS: $name found at $(command -v $cmd)"
        "$cmd" --version || true
    else
        echo "FAIL: $name not found in PATH"
        FAILED=1
    fi
}

check_cmd "java" "Java"
check_cmd "nextflow" "Nextflow"
check_cmd "docker" "Docker"

# Validate Java Version >= 17
JAVA_VER=$(java -version 2>&1 | head -n 1 | awk -F '"' '{print $2}' | cut -d'.' -f1)
if [[ "$JAVA_VER" == "1" ]]; then
    JAVA_VER=$(java -version 2>&1 | head -n 1 | awk -F '"' '{print $2}' | cut -d'.' -f2)
fi
if [[ "$JAVA_VER" -ge 17 ]]; then
    echo "PASS: Java version is $JAVA_VER (>= 17)"
else
    echo "FAIL: Java version is $JAVA_VER (expected >= 17)"
    FAILED=1
fi

# Validate Streamlit (checking help to avoid starting server)
echo ">>> Checking Streamlit..."
# Bear-hub environment should be activated or we need to use the full path/env
# The installer creates 'bear-hub' env but doesn't activate it for the shell.
# We need to find where streamlit is.
# The installer creates 'bear-hub' env.
BEAR_ENV_PYTHON=$(conda run -n bear-hub which python)
if [ -x "$BEAR_ENV_PYTHON" ]; then
    echo "PASS: bear-hub environment python found."
    $BEAR_ENV_PYTHON -m streamlit --version
    if $BEAR_ENV_PYTHON -m streamlit run "${REPO_ROOT}/BEAR-HUB.py" --help > /dev/null 2>&1; then
         echo "PASS: streamlit run BEAR-HUB.py --help works"
    else
         echo "FAIL: streamlit run failed"
         FAILED=1
    fi
else
    echo "FAIL: Could not locate python in bear-hub env"
    FAILED=1
fi

# Optional: Docker functionality check
if [ -S /var/run/docker.sock ]; then
    echo ">>> Testing Docker functionality (pull hello-world)..."
    if docker pull hello-world >/dev/null; then
        echo "PASS: Docker pull works"
    else
        echo "WARN: Docker pull failed (network or perm issue?)"
        # Not failing the whole test for this if CLI check passed, unless strict requirement
    fi
else
    echo "WARN: /var/run/docker.sock not found. Skipping functional docker test."
fi

# Save logs
cp "${BEAR_HUB_ROOT}/install.log" "${ARTIFACTS_DIR}/install.log"

if [ $FAILED -eq 0 ]; then
    echo ">>> SMOKE TEST PASSED"
    exit 0
else
    echo ">>> SMOKE TEST FAILED"
    exit 1
fi
