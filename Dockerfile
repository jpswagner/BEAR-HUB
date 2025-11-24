# Dockerfile — BEAR-HUB (Bactopia / PORT UI)

# Imagem base com micromamba para gerenciar ambiente conda
FROM mambaorg/micromamba:1.5.10

# Cria o ambiente "bear-hub" com ferramentas de sistema e bioinfo
# - Python será instalado depois via pip (requirements.txt)
RUN micromamba create -y -n bear-hub \
    -c conda-forge -c bioconda -c defaults \
    python=3.11 \
    git \
    openjdk=11 \
    nextflow \
    bactopia \
    && micromamba clean -a -y

# Diretório de trabalho dentro do container
WORKDIR /opt/bear-hub

# Copia primeiro o requirements.txt para aproveitar cache de build
COPY requirements.txt /opt/bear-hub/requirements.txt

# Instala dependências Python do app via pip dentro do env bear-hub
RUN micromamba run -n bear-hub pip install --no-cache-dir -r requirements.txt

# Agora copia o restante do código do app
COPY . /opt/bear-hub

# (Opcional) Clonar o PORT dentro da imagem
# TODO: ajuste a URL do repositório do PORT se necessário
RUN micromamba run -n bear-hub bash -lc "\
    if [ ! -d /opt/PORT ]; then \
        git clone https://github.com/immem-hackathon-2025/PORT.git /opt/PORT; \
    fi \
"

# Variáveis de ambiente úteis
ENV PORT_MAIN_NF=/opt/PORT/main.nf \
    BEAR_HUB_OUTDIR=/bactopia_out \
    BEAR_HUB_DATA=/dados

# Porta usada pelo Streamlit
EXPOSE 8501

# Comando de entrada:
# Executa o Streamlit usando o ambiente bear-hub e o HUB.py como app principal
CMD ["micromamba", "run", "-n", "bear-hub", "streamlit", "run", "HUB.py", "--server.address=0.0.0.0", "--server.port=8501"]