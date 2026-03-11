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
    cat <<'EOF'

ERRO: 'docker' não foi encontrado no PATH.
BEAR-HUB executa o Bactopia sempre com '-profile docker',
então é obrigatório ter o Docker instalado e acessível.

Instale o Docker e tente novamente.

Sugestão rápida para Ubuntu/Debian (como root ou com sudo):

  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

Depois, adicione seu usuário ao grupo docker (opcional, mas recomendado):

  sudo usermod -aG docker "$USER"
  # faça logout/login da sessão para o grupo valer

Para outras distros/OS, veja a documentação oficial:
  https://docs.docker.com/engine/install/

EOF
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
    cat <<'EOF'

ERRO: nem 'mamba' nem 'conda' encontrados no PATH.
O BEAR-HUB usa ambientes conda para:
  - 'bear-hub' (UI em Streamlit)
  - 'bactopia' (pipeline Bactopia + Nextflow)

Sugestão rápida para instalar Miniconda (Linux x86_64):

  cd "$HOME"
  curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o miniconda.sh
  bash miniconda.sh
  # siga o instalador interativo; ao final, feche e reabra o terminal

Depois disso, verifique se o 'conda' está disponível:

  conda --version

Opcional (recomendado) – instalar mamba no ambiente base:

  conda install -n base -c conda-forge mamba

Documentação oficial do Miniconda:
  https://docs.conda.io/projects/miniconda/en/latest/

EOF
    exit 1
fi

# Usaremos ambientes locais criados em ROOT_DIR/envs para garantir total isolamento
ENVS_DIR="${ROOT_DIR}/envs"
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
echo "Depois disso, você pode subir o app com o launcher:"
echo "  cd \"${ROOT_DIR}\""
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
    echo "${CRED_FILE} já existe."
fi

# 2. config.toml: disable usage stats
CONFIG_FILE="${ST_DIR}/config.toml"
if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "Criando ${CONFIG_FILE} (desativar usage stats)..."
    cat > "${CONFIG_FILE}" <<TOML
[browser]
gatherUsageStats = false
TOML
else
    echo "${CONFIG_FILE} já existe."
    # Opcional: checar se gatherUsageStats já está lá, mas não vamos sobrescrever configs do usuário
fi

echo
echo "Instalação do BEAR-HUB finalizada."
echo "Lembre-se: o Bactopia será executado sempre com '-profile docker' pelo app."
