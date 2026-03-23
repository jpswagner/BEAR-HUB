#!/usr/bin/env bash
# install_bear.sh — BEAR-HUB installer
# ---------------------------------------------------------------------------
# Sets up two conda environments (bear-hub, bactopia) and writes configuration
# to ~/.bear-hub/config.env so the app can find its dependencies at runtime.
#
# Usage:
#   bash install_bear.sh [--bactopia-version X.Y.Z]
#
# Environment overrides:
#   BACTOPIA_VERSION   Override the pinned Bactopia version (default: 3.0.0)
# ---------------------------------------------------------------------------
set -euo pipefail

# ── Versioned defaults ────────────────────────────────────────────────────────
BACTOPIA_VERSION="${BACTOPIA_VERSION:-3.0.0}"

# ── Directories ───────────────────────────────────────────────────────────────
BEAR_HUB_ROOT="${HOME}/BEAR-HUB"
DATA_DIR="${BEAR_HUB_ROOT}/data"
OUT_DIR="${BEAR_HUB_ROOT}/bactopia_out"
# New config location (read by utils/system.py → bootstrap_bear_env_from_file)
CONFIG_DIR="${HOME}/.bear-hub"
CONFIG_FILE="${CONFIG_DIR}/config.env"
# Legacy config location kept for reference
LEGACY_CONFIG_FILE="${BEAR_HUB_ROOT}/.bear-hub.env"

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bactopia-version)
            BACTOPIA_VERSION="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Helper: get conda env prefix by name
# =============================================================================
get_env_prefix() {
    local env_name="$1"
    local output prefix solver
    # Try every available solver (mamba, micromamba, conda) in order
    for solver in "${MAMBA_BIN:-}" micromamba "${CONDA_BIN:-}"; do
        [[ -z "${solver}" ]] && continue
        command -v "${solver}" >/dev/null 2>&1 || continue
        output="$("${solver}" env list 2>/dev/null || true)"
        prefix="$(
            printf '%s\n' "${output}" | awk -v name="${env_name}" '
                NF >= 2 && $1 == name { print $NF; exit }
            '
        )"
        if [[ -n "${prefix}" ]]; then
            printf '%s\n' "${prefix}"
            return 0
        fi
    done
}

# =============================================================================
# Step 1: check_prerequisites — Docker + conda/mamba
# =============================================================================
check_prerequisites() {
    echo
    echo "=== Step 1: Checking prerequisites ==="

    # Docker
    if ! command -v docker >/dev/null 2>&1; then
        cat <<'EOF'

ERROR: 'docker' was not found in PATH.
BEAR-HUB runs Bactopia exclusively with '-profile docker', so Docker is mandatory.

Quick install for Ubuntu/Debian (as root or via sudo):

  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  # (Optional) add your user to the docker group:
  sudo usermod -aG docker "$USER"
  # Then log out and back in.

For other platforms: https://docs.docker.com/engine/install/
EOF
        exit 1
    fi
    echo "Docker found: $(command -v docker)"

    # conda / mamba
    MAMBA_BIN=""
    CONDA_BIN=""

    if command -v mamba >/dev/null 2>&1; then
        MAMBA_BIN="$(command -v mamba)"
        echo "mamba found: ${MAMBA_BIN}"
    fi
    if command -v conda >/dev/null 2>&1; then
        CONDA_BIN="$(command -v conda)"
        echo "conda found: ${CONDA_BIN}"
    fi

    if [[ -z "${MAMBA_BIN}" && -z "${CONDA_BIN}" ]]; then
        cat <<'EOF'

ERROR: neither 'mamba' nor 'conda' was found in PATH.
BEAR-HUB uses conda environments for:
  - 'bear-hub' (Streamlit UI)
  - 'bactopia' (pipeline + Nextflow)

Quick Miniconda install (Linux x86_64):

  cd "$HOME"
  curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    -o miniconda.sh
  bash miniconda.sh
  # Follow the interactive prompts, then close and reopen your terminal.

  conda --version   # verify

  # Optional (recommended) — install mamba in base:
  conda install -n base -c conda-forge mamba

Miniconda docs: https://docs.conda.io/projects/miniconda/en/latest/
EOF
        exit 1
    fi

    # Export so sub-functions can use them
    export MAMBA_BIN CONDA_BIN
}

# =============================================================================
# Step 2: setup_bear_hub_env — create/verify the 'bear-hub' conda environment
# =============================================================================
setup_bear_hub_env() {
    echo
    echo "=== Step 2: Checking 'bear-hub' environment ==="

    BEAR_PREFIX="$(get_env_prefix 'bear-hub')"

    if [[ -n "${BEAR_PREFIX}" ]]; then
        echo "'bear-hub' already exists: ${BEAR_PREFIX}"
    else
        echo "Creating 'bear-hub' environment…"
        local solver="${MAMBA_BIN:-${CONDA_BIN}}"
        "${solver}" create -y -n bear-hub \
            -c conda-forge \
            "python=3.11" "streamlit>=1.25" pyyaml pandas requests

        BEAR_PREFIX="$(get_env_prefix 'bear-hub')"
        if [[ -n "${BEAR_PREFIX}" ]]; then
            echo "'bear-hub' created: ${BEAR_PREFIX}"
        else
            echo "WARNING: 'bear-hub' created but prefix not found via 'conda env list'."
        fi
    fi

    export BEAR_PREFIX
}

# =============================================================================
# Step 3: setup_bactopia_env — create/verify 'bactopia' env + Nextflow
# =============================================================================
setup_bactopia_env() {
    echo
    echo "=== Step 3: Checking 'bactopia' environment (version ${BACTOPIA_VERSION}) ==="

    BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"

    if [[ -n "${BACTOPIA_PREFIX}" ]]; then
        echo "'bactopia' already exists: ${BACTOPIA_PREFIX}"
    else
        echo "Creating 'bactopia' environment (Bactopia==${BACTOPIA_VERSION})…"
        echo "  (Pipeline will run with '-profile docker')"
        local solver="${MAMBA_BIN:-${CONDA_BIN}}"
        "${solver}" create -y -n bactopia \
            -c conda-forge -c bioconda \
            "bactopia==${BACTOPIA_VERSION}"

        BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"
        if [[ -n "${BACTOPIA_PREFIX}" ]]; then
            echo "'bactopia' created: ${BACTOPIA_PREFIX}"
        else
            echo "WARNING: 'bactopia' created but prefix not found via 'conda env list'."
        fi
    fi

    # Ensure Nextflow is present in the bactopia environment
    _ensure_nextflow "${BACTOPIA_PREFIX:-}"

    export BACTOPIA_PREFIX
}

_ensure_nextflow() {
    local prefix="$1"
    if [[ -z "${prefix}" ]]; then
        return
    fi

    if [[ -x "${prefix}/bin/nextflow" ]]; then
        echo "Nextflow found: ${prefix}/bin/nextflow"
        return
    fi

    echo "Nextflow not found in '${prefix}/bin'. Installing via conda…"
    local solver="${MAMBA_BIN:-${CONDA_BIN}}"
    "${solver}" install -y -n bactopia \
        -c bioconda -c conda-forge nextflow || true

    # Re-check after conda install
    BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"
    prefix="${BACTOPIA_PREFIX:-${prefix}}"

    if [[ ! -x "${prefix}/bin/nextflow" ]]; then
        echo "Nextflow still missing. Downloading via get.nextflow.io…"
        mkdir -p "${prefix}/bin"
        local downloader=""
        if command -v curl >/dev/null 2>&1; then
            downloader="curl"
            (cd "${prefix}/bin" && curl -fsSL https://get.nextflow.io -o nextflow)
        elif command -v wget >/dev/null 2>&1; then
            downloader="wget"
            (cd "${prefix}/bin" && wget -qO nextflow https://get.nextflow.io)
        else
            echo "ERROR: neither 'curl' nor 'wget' found. Install one and retry."
            exit 1
        fi
        chmod +x "${prefix}/bin/nextflow"
    fi

    if [[ -x "${prefix}/bin/nextflow" ]]; then
        echo "Nextflow ready: ${prefix}/bin/nextflow"
    else
        echo "ERROR: could not install Nextflow. Check the 'bactopia' environment."
        exit 1
    fi
}

# =============================================================================
# Step 4: write_config — write ~/.bear-hub/config.env
# =============================================================================
write_config() {
    echo
    echo "=== Step 4: Writing configuration ==="

    mkdir -p "${BEAR_HUB_ROOT}" "${DATA_DIR}" "${OUT_DIR}" "${CONFIG_DIR}"

    local nxf_solver=""
    if [[ -n "${MAMBA_BIN:-}" ]]; then
        nxf_solver="${MAMBA_BIN}"
    fi

    # Primary config (new location read by refactored BEAR-HUB)
    {
        echo "# Generated by install_bear.sh — edit to change default directories."
        echo "# This file is read by BEAR-HUB at startup (utils/system.py)."
        echo ""
        echo "export BEAR_HUB_ROOT=\"${BEAR_HUB_ROOT}\""
        echo "export BEAR_HUB_BASEDIR=\"${DATA_DIR}\""
        echo "export BEAR_HUB_OUTDIR=\"${OUT_DIR}\""
        echo "export BEAR_HUB_DATA=\"${DATA_DIR}\""
        echo ""
        echo "# Bactopia conda environment (provides Nextflow)"
        if [[ -n "${BACTOPIA_PREFIX:-}" ]]; then
            echo "export BACTOPIA_ENV_PREFIX=\"${BACTOPIA_PREFIX}\""
        else
            echo "WARNING: could not determine BACTOPIA_ENV_PREFIX — Nextflow may not be found by the app." >&2
            echo "# BACTOPIA_ENV_PREFIX not detected — set manually if needed"
        fi
        if [[ -n "${nxf_solver}" ]]; then
            echo "export NXF_CONDA_EXE=\"${nxf_solver}\""
        else
            echo "# NXF_CONDA_EXE not set (mamba not found at install time)"
        fi
        echo ""
        echo "# Pinned Bactopia version used during installation"
        echo "export BACTOPIA_VERSION=\"${BACTOPIA_VERSION}\""
    } > "${CONFIG_FILE}"
    echo "Config written to: ${CONFIG_FILE}"

    # Legacy symlink / copy for backward compatibility
    if [[ ! -f "${LEGACY_CONFIG_FILE}" ]]; then
        cp "${CONFIG_FILE}" "${LEGACY_CONFIG_FILE}" 2>/dev/null || true
        echo "Legacy config also written to: ${LEGACY_CONFIG_FILE}"
    fi

    echo
    echo "To load the config in your current shell:"
    echo "  source \"${CONFIG_FILE}\""
    echo
    echo "To start BEAR-HUB:"
    echo "  cd \"${BEAR_HUB_ROOT}\""
    echo "  ./run_bear.sh"
}

# =============================================================================
# Step 5: configure_streamlit — suppress first-run prompts
# =============================================================================
configure_streamlit() {
    echo
    echo "=== Step 5: Configuring Streamlit ==="

    local st_dir="${HOME}/.streamlit"
    mkdir -p "${st_dir}"

    # Suppress email prompt
    local cred_file="${st_dir}/credentials.toml"
    if [[ ! -f "${cred_file}" ]]; then
        echo "Creating ${cred_file}…"
        cat > "${cred_file}" <<'TOML'
[general]
email = ""
TOML
    else
        echo "${cred_file} already exists — skipping."
    fi

    # Disable usage stats
    local config_file="${st_dir}/config.toml"
    if [[ ! -f "${config_file}" ]]; then
        echo "Creating ${config_file}…"
        cat > "${config_file}" <<'TOML'
[browser]
gatherUsageStats = false
TOML
    else
        echo "${config_file} already exists — skipping."
    fi
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo "======================================="
    echo "  BEAR-HUB Installer"
    echo "  Bactopia version: ${BACTOPIA_VERSION}"
    echo "======================================="
    echo "BEAR_HUB_ROOT : ${BEAR_HUB_ROOT}"
    echo "DATA_DIR      : ${DATA_DIR}"
    echo "OUT_DIR       : ${OUT_DIR}"
    echo "CONFIG_FILE   : ${CONFIG_FILE}"

    check_prerequisites
    setup_bear_hub_env
    setup_bactopia_env
    write_config
    configure_streamlit

    echo
    echo "======================================="
    echo "  Installation complete!"
    echo "======================================="
    echo
    echo "Next steps:"
    echo "  source \"${CONFIG_FILE}\""
    echo "  cd \"${BEAR_HUB_ROOT}\""
    echo "  ./run_bear.sh"
    echo
    echo "Bactopia will run via '-profile docker' — make sure Docker is running."
}

main "$@"
