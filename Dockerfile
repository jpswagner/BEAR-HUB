# Dockerfile — BEAR-HUB (Bactopia / PORT UI)

# Imagem base com micromamba para gerenciar ambiente conda
FROM mambaorg/micromamba:1.5.10

# Evita problemas de lock do mamba/micromamba
ENV MAMBA_ROOT_PREFIX=/opt/conda \
    MAMBA_NO_BANNER=1 \
    MAMBA_NO_LOCK=1

# Cria o ambiente "bear-hub" com ferramentas de sistema e bioinfo
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

# Variáveis de ambiente úteis + PATH do ambiente bear-hub
ENV PORT_MAIN_NF=/opt/PORT/main.nf \
    BEAR_HUB_OUTDIR=/bactopia_out \
    BEAR_HUB_DATA=/dados \
    PATH=/opt/conda/envs/bear-hub/bin:$PATH

# Porta usada pelo Streamlit
EXPOSE 8501

# Remove o entrypoint padrão da imagem micromamba (que usa "micromamba run ...")
ENTRYPOINT []

# Comando de entrada:
# Executa o Streamlit diretamente (já com o PATH apontando para o env bear-hub)
CMD ["bash", "-lc", "streamlit run HUB.py --server.address=0.0.0.0 --server.port=8501"]
