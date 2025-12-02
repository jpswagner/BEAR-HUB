#!/usr/bin/env bash
set -euo pipefail

# Descobre a pasta onde o script está (raiz do BEAR-HUB)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==============================="
echo "  BEAR-HUB - Launcher"
echo "==============================="
echo "ROOT_DIR: ${ROOT_DIR}"

CONFIG_FILE="${ROOT_DIR}/.bear-hub.env"

# Carrega configuração gerada pelo install_bear.sh (se existir)
if [[ -f "${CONFIG_FILE}" ]]; then
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
  echo "AVISO: ${CONFIG_FILE} não encontrado."
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

# ---------------------------------------------------------
# Checagem AMIGÁVEL do ambiente 'bear-hub'
#   - Usa conda env list se existir
#   - Se não achar, só avisa e segue em frente
# ---------------------------------------------------------
ENV_LIST=""
CHECK_TOOL=""

if command -v conda >/dev/null 2>&1; then
  CHECK_TOOL="conda"
  ENV_LIST="$(conda env list 2>/dev/null || true)"
elif command -v mamba >/dev/null 2>&1; then
  CHECK_TOOL="mamba"
  ENV_LIST="$(mamba env list 2>/dev/null || true)"
fi

if [[ -n "${ENV_LIST}" ]]; then
  if printf '%s\n' "${ENV_LIST}" | grep -Eq '^[[:space:]]*bear-hub[[:space:]]'; then
    echo "Ambiente 'bear-hub' encontrado via '${CHECK_TOOL} env list'."
  else
    echo "AVISO: ambiente 'bear-hub' não apareceu em '${CHECK_TOOL} env list'."
    echo "Saída de '${CHECK_TOOL} env list':"
    printf '%s\n' "${ENV_LIST}" | sed 's/^/  /'
    echo
    echo "Vou tentar rodar mesmo assim com:"
    echo "  ${RUNNER} run -n bear-hub ..."
  fi
else
  echo "AVISO: não consegui obter lista de ambientes via conda/mamba."
  echo "Vou tentar rodar mesmo assim com:"
  echo "  ${RUNNER} run -n bear-hub ..."
fi

echo
echo "Usando: ${RUNNER} run -n bear-hub streamlit run ${APP_FILE}"
echo "Você pode passar opções do Streamlit, por exemplo:"
echo "  ./run_bear.sh --server.port 8502"
echo

cd "${ROOT_DIR}"

# IMPORTANTE:
# - '.bear-hub.env' já ajustou BEAR_HUB_ROOT/BASEDIR/OUTDIR etc.
# - '${RUNNER} run -n bear-hub' cria o processo dentro do env bear-hub.
exec "${RUNNER}" run -n bear-hub streamlit run "${APP_FILE}" "$@"
