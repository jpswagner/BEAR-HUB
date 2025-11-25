#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="bear-hub"
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== BEAR-HUB :: iniciando interface web =="

# 1) Verifica conda
if ! command -v conda >/dev/null 2>&1; then
  echo "Erro: 'conda' não encontrado no PATH."
  echo "Primeiro rode o instalador:  ./install_local.sh"
  exit 1
fi

# 2) Verifica se o ambiente existe
if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Erro: ambiente '$ENV_NAME' não encontrado."
  echo "Rode o instalador:  ./install_local.sh"
  exit 1
fi

cd "$THIS_DIR"

URL="http://localhost:8501"
echo "[info] Vou abrir o BEAR-HUB em: $URL"

# 3) Tenta abrir o navegador automaticamente (não é obrigatório)
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
fi

# 4) Sobe o app Streamlit
conda run -n "$ENV_NAME" streamlit run BEAR-HUB.py \
  --server.port 8501 \
  --server.address 0.0.0.0

