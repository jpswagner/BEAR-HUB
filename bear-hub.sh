#!/usr/bin/env bash
set -euo pipefail

IMAGE="${BEAR_IMAGE:-bear-hub}"
DATA_DIR="${BEAR_DATA:-$HOME/BEAR_DATA}"
OUT_DIR="${BEAR_OUT:-$HOME/BEAR_OUT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Flag opcional --rebuild
REBUILD=false
if [[ "${1:-}" == "--rebuild" ]]; then
  REBUILD=true
  shift
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: 'docker' não encontrado no PATH."
  exit 1
fi

# Se a imagem não existe OU --rebuild foi passado, constrói
if $REBUILD || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo ">> Construindo imagem '$IMAGE' a partir de: $SCRIPT_DIR"
  docker build -t "$IMAGE" "$SCRIPT_DIR"
  echo ">> Imagem '$IMAGE' construída com sucesso."
else
  echo ">> Imagem Docker '$IMAGE' já existe. Pulando build."
fi

mkdir -p "$DATA_DIR" "$OUT_DIR"

URL="http://localhost:8501"
echo "== BEAR-HUB =="
echo "Dados de entrada (host): $DATA_DIR"
echo "Resultados saída (host): $OUT_DIR"
echo
echo "Abrindo em: $URL"
echo

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
fi

docker run --rm -it \
  -p 8501:8501 \
  -v "$DATA_DIR":/dados \
  -v "$OUT_DIR":/bactopia_out \
  -v /:/hostfs:ro \
  "$IMAGE"
