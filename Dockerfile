# Dockerfile — BEAR-HUB

FROM mambaorg/micromamba:1.5.10

# Cria o ambiente "bear-hub" com tudo que precisa pra rodar Bactopia / Nextflow
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

# Instala dependências Python do app (incluindo streamlit) DENTRO do env bear-hub
RUN micromamba run -n bear-hub pip install --no-cache-dir -r requirements.txt

# Agora copia o restante do código do app
COPY . /opt/bear-hub

# Variáveis de ambiente úteis
ENV BEAR_HUB_OUTDIR=/bactopia_out \
    BEAR_HUB_DATA=/dados \
    MAMBA_ROOT_PREFIX=/opt/conda \
    PATH=/opt/conda/envs/bear-hub/bin:$PATH

# Porta usada pelo Streamlit
EXPOSE 8501

# Comando de entrada: agora o 'streamlit' está no PATH (env bear-hub)
CMD ["streamlit", "run", "HUB.py", "--server.address=0.0.0.0", "--server.port=8501"]
