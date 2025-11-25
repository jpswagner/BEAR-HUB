#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="bear-hub"
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== BEAR-HUB :: iniciando interface web =="

# 1) Conferir se o conda existe
if ! command -v conda >/dev/null 2>&1; then
  echo "Erro: 'conda' não encontrado no PATH."
  echo "Instale Miniconda/Conda primeiro e depois rode:  ./install_bear.sh"
  exit 1
fi

# 2) Conferir se o ambiente bear-hub existe
if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Erro: ambiente '$ENV_NAME' não encontrado."
  echo "Rode primeiro:  ./install_bear.sh"
  exit 1
fi

# 3) Ir para a pasta do projeto (onde está o app.py)
cd "$THIS_DIR"

echo "[info] Vou abrir o BEAR-HUB em: http://localhost:8501"

# 4) Rodar o Streamlit *dentro* do env bear-hub
exec conda run -n "$ENV_NAME" streamlit run app.py \
  --server.port 8501 \
  --server.address 0.0.0.0
