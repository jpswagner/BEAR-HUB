#!/usr/bin/env bash
set -euo pipefail

echo "==============================="
echo "  Instalador BEAR-HUB (local)"
echo "==============================="

# ----------------- Configuração básica -----------------
CONDA_ENV_NAME="bear-hub"

# Diretório onde está o repositório (raiz do app)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAR_ROOT="$SCRIPT_DIR"

# Diretório para dados do BEAR (pode mudar se quiser)
BEAR_DATA="${HOME}/BEAR_DATA"
BACTOPIA_DL="${BEAR_DATA}/bactopia-downloads"

echo "BEAR_ROOT:  $BEAR_ROOT"
echo "BEAR_DATA:  $BEAR_DATA"
echo "Bactopia DL: $BACTOPIA_DL"
echo

mkdir -p "$BEAR_DATA" "$BACTOPIA_DL"

# ----------------- Verifica Conda -----------------
if ! command -v conda >/dev/null 2>&1; then
  echo "ERRO: 'conda' não encontrado no PATH."
  echo "Instale Miniconda/Anaconda e depois rode novamente:  ./install_bear.sh"
  exit 1
fi

CONDA_BASE="$(conda info --base)"
# habilita 'conda activate' dentro do script
# shellcheck source=/dev/null
source "${CONDA_BASE}/etc/profile.d/conda.sh"

# ----------------- Cria/ativa env do BEAR-HUB -----------------
if ! conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV_NAME"; then
  echo "==> Criando environment Conda '${CONDA_ENV_NAME}'..."
  conda create -y -n "$CONDA_ENV_NAME" python=3.11
else
  echo "==> Environment Conda '${CONDA_ENV_NAME}' já existe, reutilizando..."
fi

echo "==> Ativando environment '${CONDA_ENV_NAME}'..."
conda activate "$CONDA_ENV_NAME"

# ----------------- Instala mamba (se não existir) -----------------
if ! command -v mamba >/dev/null 2>&1; then
  echo "==> Instalando mamba dentro do env '${CONDA_ENV_NAME}'..."
  conda install -y mamba
else
  echo "==> mamba já está instalado."
fi

# ----------------- Instala Bactopia -----------------
echo "==> Instalando Bactopia (via mamba, pode demorar)..."
mamba install -y -c conda-forge -c bioconda bactopia

# ----------------- Dependências Python do app -----------------
if [ -f "${BEAR_ROOT}/requirements.txt" ]; then
  echo "==> Instalando dependências Python do BEAR-HUB (requirements.txt)..."
  pip install -r "${BEAR_ROOT}/requirements.txt"
else
  echo "==> Nenhum requirements.txt encontrado; pulando instalação de deps Python."
fi

# ----------------- Configura NXF_CONDA_EXE e diretório de download -----------------
MAMBA_BIN="$(command -v mamba)"

echo
echo "==> Configurando variáveis de ambiente no ~/.bashrc"
echo "   - NXF_CONDA_EXE=$MAMBA_BIN"
echo "   - BEAR_BACTOPIA_DOWNLOAD_DIR=$BACTOPIA_DL"

{
  echo ""
  echo "# >>> Configuração BEAR-HUB / Bactopia >>>"
  echo "export NXF_CONDA_EXE=\"$MAMBA_BIN\""
  echo "export BEAR_BACTOPIA_DOWNLOAD_DIR=\"$BACTOPIA_DL\""
  echo "# <<< Fim da configuração BEAR-HUB / Bactopia <<<"
} >> "${HOME}/.bashrc"

# Também exporta para a sessão atual, para o download abaixo
export NXF_CONDA_EXE="$MAMBA_BIN"
export BEAR_BACTOPIA_DOWNLOAD_DIR="$BACTOPIA_DL"

# ----------------- Pré-download do Bactopia -----------------
echo
echo "==> Rodando 'bactopia download' (pode demorar bastante na primeira vez)..."
bactopia download \
  --conda \
  --bactopia \
  --tools \
  --outdir "$BACTOPIA_DL" \
  --force

echo
echo "==> Criando script de execução ${BEAR_ROOT}/run_bear.sh"

cat > "${BEAR_ROOT}/run_bear.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail

CONDA_BASE="${CONDA_BASE}"

# habilita conda
# shellcheck source=/dev/null
source "\${CONDA_BASE}/etc/profile.d/conda.sh"

conda activate "$CONDA_ENV_NAME"

export NXF_CONDA_EXE="$MAMBA_BIN"
export BEAR_BACTOPIA_DOWNLOAD_DIR="$BACTOPIA_DL"

cd "$BEAR_ROOT"
streamlit run app.py
EOF

chmod +x "${BEAR_ROOT}/run_bear.sh"

echo
echo "==============================="
echo "  Instalação concluída!"
echo "==============================="
echo
echo "Antes de rodar o BEAR-HUB:"
echo "  - Abra um NOVO terminal (ou rode: 'source ~/.bashrc')"
echo
echo "Para iniciar o app:"
echo "  cd \"$BEAR_ROOT\""
echo "  ./run_bear.sh"
echo
