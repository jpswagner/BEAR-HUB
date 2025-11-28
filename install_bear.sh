#!/usr/bin/env bash
set -euo pipefail

echo "==============================="
echo "  BEAR-HUB - Instalador"
echo "  (modo local, Bactopia via Docker)"
echo "==============================="

ROOT_DIR="${HOME}/BEAR-HUB"
DATA_DIR="${ROOT_DIR}/data"
OUT_DIR="${ROOT_DIR}/bactopia_out"

echo "ROOT_DIR: ${ROOT_DIR}"
echo "DATA_DIR: ${DATA_DIR}"
echo "OUT_DIR : ${OUT_DIR}"

mkdir -p "${ROOT_DIR}" "${DATA_DIR}" "${OUT_DIR}"

# ---------------------------------------------------------
# Verificar Docker (obrigatório para Bactopia)
# ---------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo
    echo "ERRO: 'docker' não foi encontrado no PATH."
    echo "BEAR-HUB executa o Bactopia sempre com '-profile docker',"
    echo "então é obrigatório ter o Docker instalado e acessível."
    echo
    echo "Instale o Docker (ou rootless/docker desktop) e tente novamente."
    exit 1
fi

echo
echo "Docker encontrado em: $(command -v docker)"

# ---------------------------------------------------------
# Detectar mamba/conda
# ---------------------------------------------------------
MAMBA_BIN=""
CONDA_BIN=""

if command -v mamba >/dev/null 2>&1; then
    MAMBA_BIN="$(command -v mamba)"
    echo
    echo "Usando mamba para criar ambientes."
    echo "MAMBA_BIN: ${MAMBA_BIN}"
fi

if command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
fi

if [[ -z "${MAMBA_BIN}" && -z "${CONDA_BIN}" ]]; then
    echo
    echo "ERRO: nem 'mamba' nem 'conda' encontrados no PATH."
    echo "Instale Miniconda/Mamba e tente novamente."
    exit 1
fi

# Vamos usar:
# - mamba para *criar* ambientes (se existir)
# - SEMPRE conda para listar ambientes (env list), porque mamba é chato nisso.

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
    # bear-hub                 /home/user/miniconda3/envs/bear-hub
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
# Criar/verificar ambiente bear-hub (UI em Streamlit)
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
# Criar/verificar ambiente bactopia (fornece Nextflow + pipeline)
# ---------------------------------------------------------
echo
echo "Verificando ambiente 'bactopia'..."

BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"

if [[ -n "${BACTOPIA_PREFIX}" ]]; then
    echo "Ambiente 'bactopia' já existe em: ${BACTOPIA_PREFIX}"
else
    echo "Criando ambiente 'bactopia' com Bactopia..."
    echo "  (o pipeline será executado com '-profile docker' pelo BEAR-HUB)"

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
# Salvar config para o app (.bear-hub.env)
#   - BEAR_HUB_ROOT: raiz do app
#   - BEAR_HUB_BASEDIR: base de dados (explorador de arquivos)
#   - BEAR_HUB_OUTDIR: outdir padrão do Bactopia
#   - BEAR_HUB_DATA: alias para DATA_DIR
#   - BACTOPIA_ENV_PREFIX: prefixo do env 'bactopia' (onde está o nextflow)
#   - NXF_CONDA_EXE (opcional): mamba como solver, se existir
# ---------------------------------------------------------
echo
echo "Localizando prefixo final do ambiente 'bactopia'..."

BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"

if [[ -n "${BACTOPIA_PREFIX}" ]]; then
    echo "Prefixo do ambiente 'bactopia': ${BACTOPIA_PREFIX}"

    # Solver de conda usado pelo Nextflow (só é relevante se algum profile usar conda;
    # como o BEAR-HUB força '-profile docker', isso fica mais como backup/compat).
    NXF_SOLVER=""
    if [[ -n "${MAMBA_BIN}" ]]; then
        NXF_SOLVER="${MAMBA_BIN}"
        echo "NXF_CONDA_EXE será configurado para usar: ${NXF_SOLVER}"
    else
        echo "AVISO: mamba não encontrado, NXF_CONDA_EXE não será definido (Nextflow usará 'conda' se precisar)."
    fi

    CONFIG_FILE="${ROOT_DIR}/.bear-hub.env"
    {
        echo "# Arquivo gerado pelo install_bear.sh"
        echo "# Ajuste manualmente se quiser trocar diretórios padrão."
        echo "export BEAR_HUB_ROOT=\"${ROOT_DIR}\""
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
    echo "Depois disso, ative o ambiente da UI e rode o app, por exemplo:"
    echo "  conda activate bear-hub"
    echo "  streamlit run app_bactopia_main.py"
else
    echo
    echo "ERRO: não foi possível encontrar o prefixo do ambiente 'bactopia' via 'conda env list'."
    echo "Verifique manualmente com:"
    echo "  conda env list"
fi

echo
echo "Instalação do BEAR-HUB finalizada."
echo "Lembre-se: o Bactopia será executado sempre com '-profile docker' pelo app."
