<p align="center">
<img width="480" height="480" alt="Gemini_Generated_Image_dr7x8bdr7x8bdr7x" src="https://github.com/user-attachments/assets/6d23dc4b-fc4d-4fa7-9b2a-e55adb623598" />
</p>

# BEAR-HUB (Bacterial Epidemiology & AMR Reporter - HUB) — EM DESENVOLVIMENTO

Interface simples e opinativa em **Streamlit** para orquestrar ferramentas de bioinformática:

- **Bactopia** (pipeline e Tools) via **Nextflow**
- **PORT** (assemblies Nanopore/Illumina) via Nextflow

---

# Guia de Instalação — BEAR-HUB (via Docker)

Este guia descreve como instalar e executar o **BEAR-HUB** exclusivamente em modo **Docker**.

A imagem Docker contém:

- Python + Streamlit + dependências do app
- Nextflow + Java
- Bactopia
- (Opcional) PORT clonado dentro da imagem

---

## 1. Pré-requisitos

- Linux x86_64  
- Docker instalado e funcionando

Verifique:

```bash
docker --version
```

Se der erro, instale e/ou configure o Docker antes de continuar.

## Instalação e execução (via Docker)

O BEAR-HUB foi pensado para rodar **inteiro dentro de um container Docker**, sem precisar configurar Python, Nextflow ou Bactopia diretamente no host.

### 1. Pré-requisitos

No host, você precisa ter:

- **Git**
- **Docker** instalado e em execução  
  - Linux (recomendado)  
  - ou Windows/macOS com **Docker Desktop**

> Não é necessário instalar Python, Nextflow ou Bactopia no host. Tudo isso está dentro da imagem Docker.

---

### 2. Clonar o repositório

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

3. Rodar o script de instalação/execução
O repositório inclui um script que:

Garante a existência dos diretórios padrão no host:

~/BEAR_DATA → dados de entrada (FASTQs, assemblies, etc.)

~/BEAR_OUT → resultados (saídas do Bactopia/PORT)

Verifica se o Docker está disponível.

Constrói a imagem bear-hub (se ainda não existir).

Sobe o container mapeando portas e volumes e inicia o app Streamlit.

Primeira execução:
```bash
chmod +x bear-hub.sh
./bear-hub.sh
```

Saída esperada (exemplo):

== BEAR-HUB ==
Dados de entrada (host): /home/usuario/BEAR_DATA
Resultados saída (host): /home/usuario/BEAR_OUT

Abrindo em: http://localhost:8501
4. Acessar a interface web
Com o container rodando, abra o navegador em:

http://localhost:8501
A partir daí você pode:

Selecionar FASTQs/assemblies no diretório mapeado em /dados (host: ~/BEAR_DATA)

Acompanhar o progresso das análises

Ver os resultados em /bactopia_out (host: ~/BEAR_OUT)

5. Personalizar diretórios (opcional)
Se quiser usar outros caminhos no host, basta definir variáveis de ambiente antes de rodar o script:

```bash
BEAR_DATA=/meus_fastqs \
BEAR_OUT=/meus_resultados \
./bear-hub.sh
```

BEAR_DATA → diretório de entrada mapeado para /dados dentro do container

BEAR_OUT → diretório de saída mapeado para /bactopia_out

6. Atualizar o BEAR-HUB
Para atualizar o app para a última versão:

```bash
cd BEAR-HUB
git pull
./bear-hub.sh
```

Se o Dockerfile tiver mudado, o script vai reconstruir a imagem automaticamente (caso ainda não exista uma imagem com o nome configurado em IMAGE/BEAR_IMAGE).