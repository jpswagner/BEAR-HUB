#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="bear-hub"
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== BEAR-HUB :: instalação local com conda =="

# 1) Verifica se conda existe
if ! command -v conda >/dev/null 2>&1; then
  echo "Erro: 'conda' não encontrado no PATH."
  echo "Instale Miniconda/Conda primeiro e depois rode:  ./install_local.sh"
  exit 1
fi

# Evita plugins (mamba, etc) interferindo na criação/instalação
export CONDA_NO_PLUGINS=true

echo "[info] Verificando se o ambiente '$ENV_NAME' já existe..."
if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "[info] Ambiente '$ENV_NAME' já existe. Vou garantir Nextflow/Bactopia dentro dele."
  # Garante que o env tenha tudo que o app precisa
  conda install -y -n "$ENV_NAME" \
    -c conda-forge -c bioconda -c defaults \
    openjdk=11 \
    nextflow \
    bactopia \
    git \
    pip
else
  echo "[info] Criando ambiente '$ENV_NAME' com Nextflow + Bactopia + Python..."
  conda create -y -n "$ENV_NAME" \
    -c conda-forge -c bioconda -c defaults \
    python=3.11 \
    openjdk=11 \
    nextflow \
    bactopia \
    git \
    pip
fi

echo "[info] Instalando dependências Python (Streamlit, etc) via pip no ambiente '$ENV_NAME'..."

if [[ ! -f "$THIS_DIR/requirements.txt" ]]; then
  echo "[aviso] requirements.txt não encontrado em: $THIS_DIR/requirements.txt"
  echo "        Pulei a etapa de 'pip install -r requirements.txt'."
else
  conda run -n "$ENV_NAME" python -m pip install --no-cache-dir -r "$THIS_DIR/requirements.txt"
fi

echo
echo "OK! Ambiente '$ENV_NAME' pronto."
echo "Para rodar o app, use:  ./run_bear.sh"

