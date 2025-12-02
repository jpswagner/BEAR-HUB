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

    # -----------------------------------------------------
    # Garantir que o 'nextflow' exista dentro do ambiente
    # -----------------------------------------------------
    if [[ ! -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo
        echo "nextflow não encontrado em '${BACTOPIA_PREFIX}/bin/nextflow'."
        echo "Tentando instalar nextflow dentro do ambiente 'bactopia'..."

        if [[ -n "${MAMBA_BIN}" ]]; then
            "${MAMBA_BIN}" install -y -n bactopia -c bioconda -c conda-forge nextflow || true
        else
            "${CONDA_BIN}" install -y -n bactopia -c bioconda -c conda-forge nextflow || true
        fi

        # Recarregar prefixo só por segurança (caso algo mude)
        BACTOPIA_PREFIX="$(get_env_prefix 'bactopia')"

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
    echo "  conda activate bear-hub"
    echo "  streamlit run BEAR-HUB.py"
else
    echo
    echo "ERRO: não foi possível encontrar o prefixo do ambiente 'bactopia' via 'conda env list'."
    echo "Verifique manualmente com:"
    echo "  conda env list"
fi

echo
echo "Instalação do BEAR-HUB finalizada."
echo "Lembre-se: o Bactopia será executado sempre com '-profile docker' pelo app."
