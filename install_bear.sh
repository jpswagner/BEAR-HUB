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

# Usaremos ambientes locais criados em BEAR_HUB_ROOT/envs para garantir total isolamento
ENVS_DIR="${BEAR_HUB_ROOT}/envs"
mkdir -p "${ENVS_DIR}"

BEAR_PREFIX="${ENVS_DIR}/bear-hub"
BACTOPIA_PREFIX="${ENVS_DIR}/bactopia"

# ---------------------------------------------------------
# Criar/verificar ambiente bear-hub (UI em Streamlit)
# ---------------------------------------------------------
echo
echo "Verificando ambiente 'bear-hub'..."

if [[ -d "${BEAR_PREFIX}/bin" ]]; then
    echo "Ambiente 'bear-hub' já existe em: ${BEAR_PREFIX}"
else
    echo "Criando ambiente 'bear-hub' em ${BEAR_PREFIX}..."

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" create -y -p "${BEAR_PREFIX}" -c conda-forge python=3.11 streamlit pyyaml
    else
        "${CONDA_BIN}" create -y -p "${BEAR_PREFIX}" -c conda-forge python=3.11 streamlit pyyaml
    fi
    echo "Ambiente 'bear-hub' criado em: ${BEAR_PREFIX}"
fi

# ---------------------------------------------------------
# Criar/verificar ambiente bactopia (fornece Nextflow + pipeline)
# ---------------------------------------------------------
echo
echo "Verificando ambiente 'bactopia'..."

if [[ -d "${BACTOPIA_PREFIX}/bin" ]]; then
    echo "Ambiente 'bactopia' já existe em: ${BACTOPIA_PREFIX}"
else
    echo "Criando ambiente 'bactopia' em ${BACTOPIA_PREFIX} com Bactopia..."
    echo "  (o pipeline será executado com '-profile docker' pelo BEAR-HUB)"

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" create -y -p "${BACTOPIA_PREFIX}" -c conda-forge -c bioconda bactopia
    else
        "${CONDA_BIN}" create -y -p "${BACTOPIA_PREFIX}" -c conda-forge -c bioconda bactopia
    fi
    echo "Ambiente 'bactopia' criado em: ${BACTOPIA_PREFIX}"
fi

# ---------------------------------------------------------
# Salvar config para o app (.bear-hub.env)
#   - BEAR_HUB_ROOT: raiz do app
#   - BEAR_HUB_BASEDIR: base de dados (explorador de arquivos)
#   - BEAR_HUB_OUTDIR: outdir padrão do Bactopia
#   - BEAR_HUB_DATA: alias para DATA_DIR
#   - BACTOPIA_ENV_PREFIX: prefixo do env 'bactopia' (onde está o nextflow)
#   - NXF_CONDA_EXE (opcional): mamba como solver, se existir
# ---------------------------------------------------------
echo
echo "Prefixo do ambiente 'bactopia': ${BACTOPIA_PREFIX}"

# -----------------------------------------------------
# Garantir que o 'nextflow' exista dentro do ambiente
# -----------------------------------------------------
if [[ ! -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
    echo
    echo "nextflow não encontrado em '${BACTOPIA_PREFIX}/bin/nextflow'."
    echo "Tentando instalar nextflow dentro do ambiente 'bactopia'..."

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" install -y -p "${BACTOPIA_PREFIX}" -c bioconda -c conda-forge nextflow || true
    else
        "${CONDA_BIN}" install -y -p "${BACTOPIA_PREFIX}" -c bioconda -c conda-forge nextflow || true
    fi

    # Se ainda não apareceu, baixa via get.nextflow.io
    if [[ ! -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo
        echo "ATENÇÃO: 'nextflow' ainda não foi encontrado em '${BACTOPIA_PREFIX}/bin/nextflow'."
        echo "Baixando nextflow pelo script oficial (get.nextflow.io)..."

        mkdir -p "${BACTOPIA_PREFIX}/bin"

        if command -v curl >/dev/null 2>&1; then
            (
                cd "${BACTOPIA_PREFIX}/bin"
                curl -fsSL https://get.nextflow.io -o nextflow
            )
        elif command -v wget >/dev/null 2>&1; then
            (
                cd "${BACTOPIA_PREFIX}/bin"
                wget -qO nextflow https://get.nextflow.io
            )
        else
            echo
            echo "ERRO: nem 'curl' nem 'wget' encontrados para baixar nextflow."
            echo "Instale 'curl' ou 'wget' e rode novamente 'install_bear.sh',"
            echo "ou instale manualmente o binário em '${BACTOPIA_PREFIX}/bin/nextflow'."
            exit 1
        fi

        chmod +x "${BACTOPIA_PREFIX}/bin/nextflow"
    fi

    # Checagem final
    if [[ -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo "nextflow disponível em: ${BACTOPIA_PREFIX}/bin/nextflow"
    else
        echo
        echo "ERRO: não foi possível garantir um 'nextflow' utilizável."
        echo "Verifique a instalação do ambiente 'bactopia' e rode o instalador novamente."
        exit 1
    fi
else
    echo "nextflow já encontrado em: ${BACTOPIA_PREFIX}/bin/nextflow"
fi

# Solver de conda usado pelo Nextflow
NXF_SOLVER=""
if [[ -n "${MAMBA_BIN}" ]]; then
    NXF_SOLVER="${MAMBA_BIN}"
    echo "NXF_CONDA_EXE será configurado para usar: ${NXF_SOLVER}"
else
    echo "AVISO: mamba não encontrado, NXF_CONDA_EXE não será definido (Nextflow usará 'conda' se precisar)."
fi

{
    echo "# Arquivo gerado pelo install_bear.sh"
    echo "# Ajuste manualmente se quiser trocar diretórios padrão."
    echo "export BEAR_HUB_ROOT=\"${BEAR_HUB_ROOT}\""
    echo "export BEAR_HUB_BASEDIR=\"${DATA_DIR}\""
    echo "export BEAR_HUB_OUTDIR=\"${OUT_DIR}\""
    echo "export BEAR_HUB_DATA=\"${DATA_DIR}\""
    echo
    echo "# Ambiente onde está o Nextflow/Bactopia"
    echo "export BACTOPIA_ENV_PREFIX=\"${BACTOPIA_PREFIX}\""
    if [[ -n "${NXF_SOLVER}" ]]; then
        echo "export NXF_CONDA_EXE=\"${NXF_SOLVER}\""
    else
        echo "# NXF_CONDA_EXE não definido (mamba não encontrado quando install_bear.sh foi executado)"
    fi
} > "${CONFIG_FILE}"

echo
echo "Config salva em: ${CONFIG_FILE}"
echo "Para usar no shell atual, execute:"
echo "  source \"${CONFIG_FILE}\""
echo
echo "Depois disso, você pode subir o app com o launcher:"
echo "  cd \"${BEAR_HUB_ROOT}\""
echo "  ./run_bear.sh"
echo
echo "Ou manualmente, por exemplo:"
echo "  conda run -p \"${BEAR_PREFIX}\" streamlit run BEAR-HUB.py"

# ---------------------------------------------------------
# Configuração do Streamlit para evitar prompts de primeiro uso
# - Cria ~/.streamlit/credentials.toml (suprimir email prompt)
# - Cria ~/.streamlit/config.toml (suprimir usage stats)
# ---------------------------------------------------------
echo
echo "Configurando Streamlit para evitar prompts interativos..."
ST_DIR="${HOME}/.streamlit"
mkdir -p "${ST_DIR}"

# 1. credentials.toml: suppress email prompt by setting empty email
CRED_FILE="${ST_DIR}/credentials.toml"
if [[ ! -f "${CRED_FILE}" ]]; then
    echo "Criando ${CRED_FILE}..."
    cat > "${CRED_FILE}" <<TOML
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
