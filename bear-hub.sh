#!/usr/bin/env bash
set -euo pipefail

# Nome da imagem (pode sobrescrever com BEAR_IMAGE, se quiser)
IMAGE="${BEAR_IMAGE:-bear-hub}"

# Diretórios padrão no host (podem ser sobrescritos com BEAR_DATA / BEAR_OUT)
DATA_DIR="${BEAR_DATA:-$HOME/BEAR_DATA}"   # entradas (FASTQs, assemblies, etc.)
OUT_DIR="${BEAR_OUT:-$HOME/BEAR_OUT}"      # saídas (resultados)

# Diretório da raiz do repo (onde está o Dockerfile)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ------------------------ Parse de argumentos ------------------------
REBUILD=false

for arg in "$@"; do
  if [[ "$arg" == "--rebuild" ]]; then
    REBUILD=true
  fi
done

# ------------------------ Checks básicos ------------------------
# 1) Checa se Docker está instalado
if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: 'docker' não encontrado no PATH."
  echo "Instale Docker antes de rodar o BEAR-HUB."
  exit 1
fi

# 2) Decide se precisa construir a imagem
if $REBUILD; then
  echo ">> '--rebuild' especificado. Reconstruindo a imagem '$IMAGE'."
  docker build -t "$IMAGE" "$SCRIPT_DIR"
elif ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo ">> Imagem '$IMAGE' não encontrada. Construindo a partir de: $SCRIPT_DIR"
  docker build -t "$IMAGE" "$SCRIPT_DIR"
  echo ">> Imagem '$IMAGE' construída com sucesso."
else
  echo ">> Imagem Docker '$IMAGE' já existe. Pulando build (use --rebuild para forçar)."
fi

# 3) Garante que os diretórios de dados existem
mkdir -p "$DATA_DIR" "$OUT_DIR"

URL="http://localhost:8501"

echo "== BEAR-HUB =="
echo "Dados de entrada (host): $DATA_DIR"
echo "Resultados saída (host): $OUT_DIR"
echo
echo "Abrindo em: $URL"
echo

# 3.1) Tenta abrir o navegador automaticamente (best-effort, não quebra o script)
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  # macOS
  open "$URL" >/dev/null 2>&1 || true
fi

# 4) Sobe o container
docker run --rm -it \
  -p 8501:8501 \
  -v "$DATA_DIR":/dados \
  -v "$OUT_DIR":/bactopia_out \
  -v /:/hostfs:ro \
  "$IMAGE"
