#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="bear-hub"
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_APP="BEAR-HUB.py"

echo "== BEAR-HUB :: iniciando interface web =="

# 1) Verifica se conda existe
if ! command -v conda >/dev/null 2>&1; then
  echo "Erro: 'conda' não encontrado no PATH."
  echo "Ative/instale Miniconda/Conda e rode novamente."
  exit 1
fi

# 2) Verifica se o ambiente já existe
if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Erro: ambiente '$ENV_NAME' não encontrado."
  echo "Rode primeiro:  ./install_bear.sh"
  exit 1
fi

# 3) Define outdir padrão (na própria pasta do projeto, gravável pelo usuário)
export BEAR_HUB_OUTDIR="${BEAR_HUB_OUTDIR:-"$THIS_DIR/bactopia_out"}"
mkdir -p "$BEAR_HUB_OUTDIR"

# 4) Porta do Streamlit (pode mudar com: PORT=8502 ./run_bear.sh)
PORT="${PORT:-8501}"

echo "[info] Vou abrir o BEAR-HUB em: http://localhost:${PORT}"

cd "$THIS_DIR"

# 5) Roda o Streamlit dentro do ambiente conda, apontando para BEAR-HUB.py
conda run -n "$ENV_NAME" streamlit run "$MAIN_APP" \
  --server.port "$PORT" \
  --server.address 0.0.0.0
