# Bactopia UI Local (Streamlit)

Interface simples e opinativa para orquestrar **Bactopia** (pipeline e Tools) via **Nextflow** com **Docker/Apptainer**. Focada em uso local ou em servidor on‑prem, com **presets**, **construção de comandos**, **execução assíncrona** com logs em tempo real e ações de **stop/clean**.

> **Status**: uso interno / laboratório. Sinta‑se à vontade para adaptar ao seu ambiente.

---

## Índice

* [Principais recursos](#principais-recursos)
* [Arquitetura em 1 minuto](#arquitetura-em-1-minuto)
* [Requisitos](#requisitos)
* [Instalação](#instalação)
* [Pastas e presets](#pastas-e-presets)
* [Bancos/DBs externos (Kraken2, Bakta, etc.)](#bancosdbs-externos-kraken2-bakta-etc)
* [Como usar](#como-usar)
* [Limpeza e manutenção](#limpeza-e-manutenção)
* [Licença](#licença)

---

## Principais recursos

* **UI Streamlit** para rodar *Bactopia pipeline* e *Bactopia Tools* via Nextflow.
* **Presets** (YAML) por ferramenta/pipeline para repetir execuções com segurança e reprodutibilidade.
* **Construção e pré‑visualização do comando** antes de iniciar.
* **Execução assíncrona** com captura de logs em tempo real (usa `stdbuf` quando disponível).
* **Parar/continuar/limpar** execuções diretamente pela interface.
* **Separação de páginas**: Pipeline, Tools oficiais e utilidades (ex.: cache/bases, DB helpers).
* **Compatível com Docker ou Apptainer** (Singularity) conforme o perfil do Nextflow.
* **Consciente de ambiente multiusuário**: orientações de perfis e diretórios para evitar colisões.

## Arquitetura em 1 minuto

* **Frontend**: Streamlit (Python).
* **Orquestração**: Nextflow (processos, cache, workdir, perfis, containers).

## Requisitos

* Linux x86_64.
* **Python** ≥ 3.10 (recomendado 3.11+).
* **Nextflow** ≥ 25.04 (recomendado 25.10+).
* **Container runtime**: Docker **ou** Apptainer (Singularity).
* **Bactopia** (pipeline e tools) e acesso aos **bancos de dados** necessários (Kraken2, Bakta, etc.).
* (Opcional) `stdbuf` (GNU coreutils) para melhor *streaming* de logs.

## Instalação

```bash
# 1) Clone o repositório
git clone <URL_DO_REPO> bactopia-ui
cd bactopia-ui

# 2) Ambiente Python
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# Se existir requirements.txt, preferir:
# pip install -r requirements.txt
# Caso contrário:
pip install "streamlit>=1.30" pyyaml pandas

# 3) Verifique o Nextflow e o runtime de containers
nextflow -version
Docker --version   # ou apptainer --version

# 4) Rode em modo desenvolvimento (porta padrão do Streamlit)
streamlit run app.py
```

> **Dica**: configure `~/.nextflow/config` com seus perfis (veja abaixo) antes de executar.


### Pastas e presets

* Estado local: `~/.bactopia_ui_local/`

  * Presets: `~/.bactopia_ui_local/presets.yaml`
* Saídas padrão: configuráveis na UI (há um `DEFAULT_OUTDIR` no código – ajuste conforme seu ambiente).
* É possível salvar diferentes **presets** por pipeline/tool (ex.: caminhos de FASTQs, parâmetros, perfil etc.).


## Como usar

1. Abra a UI (local ou via servidor).
2. Vá em **Pipeline** ou **Tools**.
3. Selecione o item desejado, preencha parâmetros, escolha o **perfil** e **pré‑visualize** o comando.
4. Clique em **Start** para executar. Os logs aparecem em tempo real.
5. Use **Stop** para solicitar interrupção. Após parar, use **Clean** se quiser remover *work*/cache.
6. Salve configurações frequentes em **Presets** (útil para reprodutibilidade e multiusuário).

> A UI usa um *runner* por sessão/navegador (namespace `main`). Mantenha uma aba por execução.


## Limpeza e manutenção

* Botão **Clean** tenta `nextflow clean -f <runName>`.
* Se o Nextflow reclamar de **cache ausente** (`.nextflow/cache/.../index.<run>`), faça **limpeza manual** das pastas de `work/` e `.nextflow/cache/` correspondentes (ação irreversível!).
* Rotacione/arquive logs grandes periodicamente.



## Agradecimentos

* [Bactopia](https://bactopia.github.io/), [Nextflow](https://www.nextflow.io/), [Streamlit](https://streamlit.io/).

## Licença


