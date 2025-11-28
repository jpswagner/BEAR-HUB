#!/usr/bin/env bash
set -euo pipefail

echo "==============================="
echo "  BEAR-HUB - Instalador"
echo "==============================="

ROOT_DIR="${HOME}/BEAR-HUB"
echo "ROOT_DIR: ${ROOT_DIR}"

mkdir -p "${ROOT_DIR}"

# ---------------------------------------------------------
# Detectar mamba/conda
# ---------------------------------------------------------
MAMBA_BIN=""
CONDA_BIN=""

if command -v mamba >/dev/null 2>&1; then
    MAMBA_BIN="$(command -v mamba)"
    echo "Usando mamba para criar ambientes."
    echo "MAMBA_BIN: ${MAMBA_BIN}"
fi

if command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
fi

if [[ -z "${MAMBA_BIN}" && -z "${CONDA_BIN}" ]]; then
    echo "ERRO: nem 'mamba' nem 'conda' encontrados no PATH."
    exit 1
fi

# Vamos usar:
# - mamba para *criar* ambientes (se existir)
# - SEMPRE conda para listar ambientes (env list), porque mamba está bugado aí.

# ---------------------------------------------------------
# Função para pegar o prefixo de um ambiente pelo nome
# (parseando 'conda env list' em texto, sem JSON e sem python)
# ---------------------------------------------------------
get_env_prefix() {
    local env_name="$1"

    # Se não tiver conda, não dá pra listar ambientes
    if [[ -z "${CONDA_BIN}" ]]; then
        return 0
    fi

    # Pega a saída do 'conda env list'
    # Usamos '|| true' pra não quebrar o script se der erro
    local output
    output="$("${CONDA_BIN}" env list 2>/dev/null || true)"

    # Exemplo de linhas:
    # base                     /home/user/miniconda3
    # bactopia                 /mnt/HD/conda_envs/bactopia
    #
    # E também linhas só com caminho (sem nome), que vamos ignorar:
    #                         /home/user/micromamba/envs/bactopia

    # Pegar a primeira linha onde a 1ª coluna == nome do ambiente
    local prefix
    prefix="$(
        printf '%s\n' "${output}" | awk -v name="${env_name}" '
            NF >= 2 && $1 == name { print $NF; exit }
        '
    )"

    if [[ -n "${prefix}" ]]; then
        printf '%s\n' "${prefix}"
    fi
}

# ---------------------------------------------------------
# Criar/verificar ambiente bear-hub
# ---------------------------------------------------------
echo
echo "Verificando ambiente 'bear-hub'..."

BEAR_PREFIX="$(get_env_prefix 'bear-hub')"

if [[ -n "${BEAR_PREFIX}" ]]; then
    echo "Ambiente 'bear-hub' já existe em: ${BEAR_PREFIX}"
else
    echo "Criando ambiente 'bear-hub'..."

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" create -y -n bear-hub -c conda-forge python=3.11 streamlit pyyaml
    else
        "${CONDA_BIN}" create -y -n bear-hub -c conda-forge python=3.11 streamlit pyyaml
    fi

    BEAR_PREFIX="$(get_env_prefix 'bear-hub')"
    if [[ -n "${BEAR_PREFIX}" ]]; then
        echo "Ambiente 'bear-hub' criado em: ${BEAR_PREFIX}"
    else
        echo "AVISO: ambiente 'bear-hub' criado, mas não foi possível descobrir o prefixo via 'conda env list'."
    fi
fi

# ---------------------------------------------------------
# Criar/verificar ambiente bactopia
# ---------------------------------------------------------
echo
echo "Verificando ambiente 'bactopia'..."

BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"

if [[ -n "${BACTOPIA_PREFIX}" ]]; then
    echo "Ambiente 'bactopia' já existe em: ${BACTOPIA_PREFIX}"
else
    echo "Criando ambiente 'bactopia' com Bactopia..."

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" create -y -n bactopia -c conda-forge -c bioconda bactopia
    else
        "${CONDA_BIN}" create -y -n bactopia -c conda-forge -c bioconda bactopia
    fi

    BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"
    if [[ -n "${BACTOPIA_PREFIX}" ]]; then
        echo "Ambiente 'bactopia' criado em: ${BACTOPIA_PREFIX}"
    else
        echo "AVISO: ambiente 'bactopia' criado, mas não foi possível descobrir o prefixo via 'conda env list'."
    fi
fi

# ---------------------------------------------------------
# Salvar config para o app (prefixo do bactopia + NXF_CONDA_EXE)
# ---------------------------------------------------------
echo
echo "Localizando prefixo final do ambiente 'bactopia'..."

BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"

if [[ -n "${BACTOPIA_PREFIX}" ]]; then
    echo "Prefixo do ambiente 'bactopia': ${BACTOPIA_PREFIX}"

    # Solver de conda usado pelo Nextflow
    NXF_SOLVER=""
    if [[ -n "${MAMBA_BIN}" ]]; then
        NXF_SOLVER="${MAMBA_BIN}"
        echo "NXF_CONDA_EXE será configurado para usar: ${NXF_SOLVER}"
    else
        echo "AVISO: mamba não encontrado, NXF_CONDA_EXE não será definido (Nextflow usará 'conda')."
    fi

    CONFIG_FILE="${ROOT_DIR}/.bear-hub.env"
    {
        echo "# Arquivo gerado pelo install_bear.sh"
        echo "export BEAR_HUB_ROOT=\"${ROOT_DIR}\""
        echo "export BACTOPIA_ENV_PREFIX=\"${BACTOPIA_PREFIX}\""
        if [[ -n \"${NXF_SOLVER}\" ]]; then
            echo "export NXF_CONDA_EXE=\"${NXF_SOLVER}\""
        else
            echo "# NXF_CONDA_EXE não definido (mamba não encontrado quando install_bear.sh foi executado)"
        fi
    } > "${CONFIG_FILE}"

    echo "Config salva em: ${CONFIG_FILE}"
    echo "Para usar no shell, execute:"
    echo "  source \"${CONFIG_FILE}\""
else
    echo "ERRO: não foi possível encontrar o prefixo do ambiente 'bactopia' via 'conda env list'."
    echo "Verifique manualmente com:"
    echo "  conda env list"
fi

echo
echo "Instalação do BEAR-HUB finalizada."
