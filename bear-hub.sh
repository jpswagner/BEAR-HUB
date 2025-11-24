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
if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: 'docker' não encontrado no PATH."
  echo "Instale Docker antes de rodar o BEAR-HUB."
  exit 1
fi

# ------------------------ Build da imagem ------------------------
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

# ------------------------ Diretórios de dados ------------------------
mkdir -p "$DATA_DIR" "$OUT_DIR"

URL="http://localhost:8501"

echo "== BEAR-HUB =="
echo "Dados de entrada (host): $DATA_DIR"
echo "Resultados saída (host): $OUT_DIR"
echo
echo "Abrindo em: $URL"
echo

# Tentativa best-effort de abrir o navegador
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
fi

# ------------------------ Sobe o container ------------------------
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  -p 8501:8501 \
  -v "$DATA_DIR":/dados \
  -v "$OUT_DIR":/bactopia_out \
  -v /:/hostfs:ro \
  -e BEAR_HUB_DATA=/dados \
  -e BEAR_HUB_OUT=/bactopia_out \
  -e NXF_HOME=/bactopia_out/.nextflow \
  -e NXF_WORK=/bactopia_out/work \
  "$IMAGE"
