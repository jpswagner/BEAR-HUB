cd ~/BEAR-HUB

cat > install_bear.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="bear-hub"
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== BEAR-HUB :: instalação local com conda =="

# 1) Verifica se conda está disponível
if ! command -v conda >/dev/null 2>&1; then
  echo "ERRO: 'conda' não encontrado no PATH."
  echo "Instale Miniconda/Conda primeiro e depois rode:  ./install_bear.sh"
  exit 1
fi

# Evita plugins (mamba, etc) atrapalhando
export CONDA_NO_PLUGINS=true

# 2) Descobre o prefixo base da instalação
BASE_PREFIX="$(conda info --base | tail -n 1)"
echo "[debug] BASE_PREFIX=$BASE_PREFIX"

echo "[info] Verificando se o ambiente '$ENV_NAME' já existe..."
if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "[info] Ambiente '$ENV_NAME' já existe. Vou garantir os pacotes essenciais."
  conda install -y -n "$ENV_NAME" \
    -c conda-forge -c bioconda -c defaults \
    python=3.11 \
    openjdk=11 \
    nextflow \
    bactopia \
    git \
    pip
else
  echo "[info] Ambiente '$ENV_NAME' não existe. Vou criá-lo."
  conda create -y -n "$ENV_NAME" \
    -c conda-forge -c bioconda -c defaults \
    python=3.11 \
    openjdk=11 \
    nextflow \
    bactopia \
    git \
    pip
fi

echo "[info] Instalando dependências Python do app (Streamlit etc) dentro de '$ENV_NAME'..."
if [[ -f "$THIS_DIR/requirements.txt" ]]; then
  conda run -n "$ENV_NAME" python -m pip install --no-cache-dir -r "$THIS_DIR/requirements.txt"
else
  echo "[aviso] requirements.txt não encontrado em $THIS_DIR/requirements.txt; pulando 'pip install'."
fi

# 3) Calcula o prefixo do ambiente
ENV_PREFIX="${BASE_PREFIX}/envs/${ENV_NAME}"
echo "[debug] ENV_PREFIX=$ENV_PREFIX"

# 4) Cria wrapper de 'conda' DENTRO do ambiente, pra remover --mkdir
if [[ -x "$ENV_PREFIX/bin/conda" ]]; then
  if [[ ! -x "$ENV_PREFIX/bin/conda.real" ]]; then
    echo "[info] Criando wrapper de 'conda' só dentro do ambiente '$ENV_NAME' (remoção de --mkdir)..."
    mv "$ENV_PREFIX/bin/conda" "$ENV_PREFIX/bin/conda.real"
    cat > "$ENV_PREFIX/bin/conda" << 'EOF_CONDA_WRAPPER'
#!/usr/bin/env bash
REAL_CONDA="$(dirname "$0")/conda.real"

args=()
for a in "$@"; do
  if [ "$a" = "--mkdir" ]; then
    # Versões novas do conda não suportam mais --mkdir; simplesmente ignoramos
    continue
  fi
  args+=("$a")
done

exec "$REAL_CONDA" "${args[@]}"
EOF_CONDA_WRAPPER
    chmod +x "$ENV_PREFIX/bin/conda"
  else
    echo "[info] Wrapper de 'conda' já existe em $ENV_PREFIX/bin/conda.real – não vou sobrescrever."
  fi
else
  echo "[aviso] Não encontrei $ENV_PREFIX/bin/conda;"
  echo "        Se os ambientes ficam em outro lugar, ajuste ENV_PREFIX dentro do install_bear.sh."
fi

echo
echo "OK! Ambiente '$ENV_NAME' configurado."
echo "Para rodar o BEAR-HUB, use:  ./run_bear.sh"
EOF

chmod +x install_bear.sh
