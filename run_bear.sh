#!/usr/bin/env bash
set -euo pipefail

# Descobre a pasta onde o script está (raiz do BEAR-HUB)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==============================="
echo "  BEAR-HUB - Launcher"
echo "==============================="
echo "ROOT_DIR: ${ROOT_DIR}"

# Procura o arquivo de configuração gerado pelo install_bear.sh
# Nova localização (~/.bear-hub/config.env) tem prioridade sobre a legada (ROOT_DIR/.bear-hub.env)
if [[ -f "${HOME}/.bear-hub/config.env" ]]; then
  CONFIG_FILE="${HOME}/.bear-hub/config.env"
elif [[ -f "${ROOT_DIR}/.bear-hub.env" ]]; then
  CONFIG_FILE="${ROOT_DIR}/.bear-hub.env"
else
  CONFIG_FILE=""
fi

if [[ -n "${CONFIG_FILE}" ]]; then
  echo "Carregando configuração de ${CONFIG_FILE}"
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"

  if [[ -n "${BEAR_HUB_BASEDIR:-}" ]]; then
    echo "BEAR_HUB_BASEDIR (dados): ${BEAR_HUB_BASEDIR}"
  fi
  if [[ -n "${BEAR_HUB_OUTDIR:-}" ]]; then
    echo "BEAR_HUB_OUTDIR (outdir): ${BEAR_HUB_OUTDIR}"
  fi
else
  echo "AVISO: arquivo de configuração não encontrado."
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
  echo "Certifique-se que o Miniconda/Mamba está instalado e no PATH."
  exit 1
fi

BEAR_PREFIX="${ROOT_DIR}/envs/bear-hub"

if [[ ! -d "${BEAR_PREFIX}" ]]; then
  echo "ERRO: O ambiente 'bear-hub' não foi encontrado em: ${BEAR_PREFIX}"
  echo "Execute './install_bear.sh' primeiro."
  exit 1
fi

echo
echo "Usando: ${RUNNER} run -p \"${BEAR_PREFIX}\" streamlit run ${APP_FILE}"
echo "Você pode passar opções do Streamlit, por exemplo:"
echo "  ./run_bear.sh --server.port 8502"
echo

cd "${ROOT_DIR}"

# IMPORTANTE:
# - '.bear-hub.env' já ajustou BEAR_HUB_ROOT/BASEDIR/OUTDIR etc.
# - '${RUNNER} run -p ${BEAR_PREFIX}' cria o processo dentro do env local bear-hub.
exec "${RUNNER}" run -p "${BEAR_PREFIX}" streamlit run "${APP_FILE}" "$@"
