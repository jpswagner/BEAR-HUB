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

# Se BEAR_HUB_ROOT não veio do .env, define aqui
export BEAR_HUB_ROOT="${BEAR_HUB_ROOT:-${ROOT_DIR}}"

# Apenas para log: mostra bases padrão (se existirem)
if [[ -n "${BEAR_HUB_BASEDIR:-}" ]]; then
  echo "BEAR_HUB_BASEDIR (dados): ${BEAR_HUB_BASEDIR}"
fi
if [[ -n "${BEAR_HUB_OUTDIR:-}" ]]; then
  echo "BEAR_HUB_OUTDIR (outdir): ${BEAR_HUB_OUTDIR}"
fi

# Arquivo principal do Streamlit (app multipage)
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
  echo "Certifique-se que o Miniconda/Mamba está instalado e no PATH."
  exit 1
fi

# Verifica se o ambiente bear-hub existe (só pra dar erro mais amigável)
if ! "${RUNNER}" env list 2>/dev/null | awk 'NF>=2 {print $1}' | grep -qx "bear-hub"; then
  echo "ERRO: ambiente 'bear-hub' não encontrado pelo '${RUNNER} env list'."
  echo "Execute primeiro o instalador:"
  echo "  ./install_bear.sh"
  exit 1
fi

echo
echo "Usando: ${RUNNER} run -n bear-hub ..."
echo "Se precisar, você pode passar opções do Streamlit, por exemplo:"
echo "  ./run_bear.sh --server.port 8502"
echo
echo "Lembrete: o Bactopia será executado pelo app sempre com '-profile docker'."
echo

cd "${ROOT_DIR}"

# IMPORTANTE:
# - 'source .bear-hub.env' já ajustou variáveis (BEAR_HUB_ROOT, BEAR_HUB_BASEDIR, etc)
# - '${RUNNER} run -n bear-hub' cria um processo dentro do env bear-hub,
#   preservando essas variáveis de ambiente, então o app consegue
#   encontrar o Bactopia/Nextflow e a configuração do BEAR-HUB.
exec "${RUNNER}" run -n bear-hub streamlit run "${APP_FILE}" "$@"
