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

# Conda env prefixes (local to the project tree)
ENVS_DIR="${BEAR_HUB_ROOT}/envs"
BEAR_PREFIX="${ENVS_DIR}/bear-hub"
BACTOPIA_PREFIX="${ENVS_DIR}/bactopia"

# Conda/mamba binaries (populated by check_prerequisites)
MAMBA_BIN=""
CONDA_BIN=""

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
}

# =============================================================================
# Step 2: setup_bear_hub_env — create the Streamlit UI environment
# =============================================================================
setup_bear_hub_env() {
    echo
    echo "=== Step 2: Setting up 'bear-hub' environment ==="

    mkdir -p "${ENVS_DIR}"

    if [[ -d "${BEAR_PREFIX}/bin" ]]; then
        echo "Ambiente 'bear-hub' ja existe em: ${BEAR_PREFIX}"
    else
        echo "Criando ambiente 'bear-hub' em ${BEAR_PREFIX}..."

        if [[ -n "${MAMBA_BIN}" ]]; then
            "${MAMBA_BIN}" create -y -p "${BEAR_PREFIX}" -c conda-forge \
                python=3.11 streamlit pyyaml pandas altair requests
        else
            "${CONDA_BIN}" create -y -p "${BEAR_PREFIX}" -c conda-forge \
                python=3.11 streamlit pyyaml pandas altair requests
        fi
        echo "Ambiente 'bear-hub' criado em: ${BEAR_PREFIX}"
    fi
}

# =============================================================================
# Step 3: setup_bactopia_env — create the Bactopia/Nextflow environment
# =============================================================================
setup_bactopia_env() {
    echo
    echo "=== Step 3: Setting up 'bactopia' environment ==="

    mkdir -p "${ENVS_DIR}"

    if [[ -d "${BACTOPIA_PREFIX}/bin" ]]; then
        echo "Ambiente 'bactopia' ja existe em: ${BACTOPIA_PREFIX}"
    else
        echo "Criando ambiente 'bactopia' em ${BACTOPIA_PREFIX} com Bactopia..."
        echo "  (o pipeline sera executado com '-profile docker' pelo BEAR-HUB)"

        if [[ -n "${MAMBA_BIN}" ]]; then
            "${MAMBA_BIN}" create -y -p "${BACTOPIA_PREFIX}" \
                -c conda-forge -c bioconda bactopia
        else
            "${CONDA_BIN}" create -y -p "${BACTOPIA_PREFIX}" \
                -c conda-forge -c bioconda bactopia
        fi
        echo "Ambiente 'bactopia' criado em: ${BACTOPIA_PREFIX}"
    fi

    # Ensure nextflow is available inside the bactopia environment
    ensure_nextflow
}

# =============================================================================
# Helper: ensure_nextflow — install Nextflow if missing from bactopia env
# =============================================================================
ensure_nextflow() {
    echo
    echo "Verificando nextflow no ambiente 'bactopia'..."

    if [[ -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo "nextflow ja encontrado em: ${BACTOPIA_PREFIX}/bin/nextflow"
        return 0
    fi

    echo "nextflow nao encontrado em '${BACTOPIA_PREFIX}/bin/nextflow'."
    echo "Tentando instalar nextflow dentro do ambiente 'bactopia'..."

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" install -y -p "${BACTOPIA_PREFIX}" \
            -c bioconda -c conda-forge nextflow || true
    else
        "${CONDA_BIN}" install -y -p "${BACTOPIA_PREFIX}" \
            -c bioconda -c conda-forge nextflow || true
    fi

    # If conda/mamba install didn't produce the binary, download directly
    if [[ ! -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo
        echo "ATENCAO: 'nextflow' ainda nao foi encontrado."
        echo "Baixando nextflow pelo script oficial (get.nextflow.io)..."

        mkdir -p "${BACTOPIA_PREFIX}/bin"

        if command -v curl >/dev/null 2>&1; then
            curl -fsSL https://get.nextflow.io -o "${BACTOPIA_PREFIX}/bin/nextflow"
        elif command -v wget >/dev/null 2>&1; then
            wget -qO "${BACTOPIA_PREFIX}/bin/nextflow" https://get.nextflow.io
        else
            echo
            echo "ERRO: nem 'curl' nem 'wget' encontrados para baixar nextflow."
            echo "Instale 'curl' ou 'wget' e rode novamente 'install_bear.sh',"
            echo "ou instale manualmente o binario em '${BACTOPIA_PREFIX}/bin/nextflow'."
            exit 1
        fi

        chmod +x "${BACTOPIA_PREFIX}/bin/nextflow"
    fi

    # Final check
    if [[ -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo "nextflow disponivel em: ${BACTOPIA_PREFIX}/bin/nextflow"
    else
        echo
        echo "ERRO: nao foi possivel garantir um 'nextflow' utilizavel."
        echo "Verifique a instalacao do ambiente 'bactopia' e rode o instalador novamente."
        exit 1
    fi
}

# =============================================================================
# Step 4: write_config — persist config.env for the Streamlit app
# =============================================================================
write_config() {
    echo
    echo "=== Step 4: Writing configuration ==="

    mkdir -p "${CONFIG_DIR}"
    mkdir -p "${DATA_DIR}"
    mkdir -p "${OUT_DIR}"

    # Determine NXF_CONDA_EXE (mamba preferred)
    local nxf_solver=""
    if [[ -n "${MAMBA_BIN}" ]]; then
        nxf_solver="${MAMBA_BIN}"
        echo "NXF_CONDA_EXE sera configurado para usar: ${nxf_solver}"
    else
        echo "AVISO: mamba nao encontrado, NXF_CONDA_EXE nao sera definido."
    fi

    {
        echo "# Generated by install_bear.sh — edit to change default directories."
        echo "# This file is read by BEAR-HUB at startup (utils/system.py)."
        echo
        echo "export BEAR_HUB_ROOT=\"${BEAR_HUB_ROOT}\""
        echo "export BEAR_HUB_BASEDIR=\"${DATA_DIR}\""
        echo "export BEAR_HUB_OUTDIR=\"${OUT_DIR}\""
        echo "export BEAR_HUB_DATA=\"${DATA_DIR}\""
        echo
        echo "# Bactopia conda environment (provides Nextflow)"
        echo "export BACTOPIA_ENV_PREFIX=\"${BACTOPIA_PREFIX}\""
        if [[ -n "${nxf_solver}" ]]; then
            echo "export NXF_CONDA_EXE=\"${nxf_solver}\""
        else
            echo "# NXF_CONDA_EXE nao definido (mamba nao encontrado)"
        fi
        echo
        echo "# Pinned Bactopia version used during installation"
        echo "export BACTOPIA_VERSION=\"${BACTOPIA_VERSION}\""
    } > "${CONFIG_FILE}"

    echo "Config salva em: ${CONFIG_FILE}"
}

# =============================================================================
# Step 5: configure_streamlit — suppress first-run prompts
# =============================================================================
configure_streamlit() {
    echo
    echo "=== Step 5: Configuring Streamlit ==="

    local st_dir="${HOME}/.streamlit"
    mkdir -p "${st_dir}"

    # credentials.toml: suppress email prompt
    local cred_file="${st_dir}/credentials.toml"
    if [[ ! -f "${cred_file}" ]]; then
        echo "Criando ${cred_file}..."
        cat > "${cred_file}" <<'TOML'
[general]
email = ""
TOML
    else
        echo "${cred_file} already exists — skipping."
    fi

    # config.toml: disable usage stats (only if no project-level config)
    local config_file="${st_dir}/config.toml"
    if [[ ! -f "${config_file}" ]]; then
        echo "Criando ${config_file}..."
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
    echo "  cd \"${BEAR_HUB_ROOT}/BEAR-HUB\""
    echo "  ./run_bear.sh"
    echo
    echo "Or manually:"
    echo "  conda run -p \"${BEAR_PREFIX}\" streamlit run BEAR-HUB.py"
    echo
    echo "Bactopia will run via '-profile docker' — make sure Docker is running."
}

main "$@"
