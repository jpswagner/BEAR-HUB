#!/usr/bin/env bash
set -euo pipefail

# Descobre a pasta onde o script está (raiz do BEAR-HUB)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==============================="
echo "  BEAR-HUB - Launcher"
echo "==============================="
echo "ROOT_DIR: ${ROOT_DIR}"

# Carrega configuração gerada pelo install_bear.sh (se existir)
if [[ -f "${ROOT_DIR}/.bear-hub.env" ]]; then
  echo "Carregando configuração de ${ROOT_DIR}/.bear-hub.env"
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.bear-hub.env"
else
  echo "AVISO: ${ROOT_DIR}/.bear-hub.env não encontrado."
  echo "       Execute primeiro:  ./install_bear.sh"
fi

# Arquivo principal do Streamlit
APP_FILE="${ROOT_DIR}/BEAR-HUB.py"

if [[ ! -f "${APP_FILE}" ]]; then
  echo "ERRO: arquivo principal do app não encontrado: ${APP_FILE}"
  echo "Verifique se o repositório está completo e se o nome do arquivo é BEAR-HUB.py"
  exit 1
fi

# Escolhe se vai usar mamba ou conda para rodar o app
RUNNER=""
if command -v mamba >/dev/null 2>&1; then
  RUNNER="mamba"
elif command -v conda >/dev/null 2>&1; then
  RUNNER="conda"
else
  echo "ERRO: nem 'mamba' nem 'conda' encontrados no PATH."
  echo "Certifique-se que o Miniconda está instalado e no PATH."
  exit 1
fi

echo "Usando: ${RUNNER} run -n bear-hub ..."
echo "Se precisar, você pode passar opções do Streamlit, ex.:"
echo "  ./run_bear.sh --server.port 8502"
echo

cd "${ROOT_DIR}"

# IMPORTANTE:
# - 'source .bear-hub.env' já ajustou PATH (incluindo o bin do ambiente bactopia)
# - '${RUNNER} run -n bear-hub' cria um processo dentro do env bear-hub,
#   preservando esse PATH estendido, então o app ainda enxerga 'nextflow', 'bactopia', etc.
exec "${RUNNER}" run -n bear-hub streamlit run "${APP_FILE}" "$@"
