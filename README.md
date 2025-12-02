<p align="center">
<img width="480" height="480" alt="Gemini_Generated_Image_dr7x8bdr7x8bdr7x" src="https://github.com/user-attachments/assets/6d23dc4b-fc4d-4fa7-9b2a-e55adb623598" />
</p>

# 🐻 BEAR-HUB  
**Bacterial Epidemiology & AMR Reporter — HUB** - (EM DESENVOLVIMENTO)

BEAR-HUB é uma interface simples em **Streamlit** para orquestrar pipelines de epidemiologia bacteriana e resistência antimicrobiana:

- **Bactopia** (pipeline principal com geração automática de FOFN)
- **Ferramentas Bactopia (`--wf`)** em amostras já concluídas  
- **PORT** (suporte a assemblies híbridos / Nanopore + Illumina – em desenvolvimento)

O objetivo é ter um ponto único para rodar análises reprodutíveis usando **Nextflow + Bactopia**, com uma interface gráfica leve.

---

## 🔧 1. Requisitos

Por enquanto o BEAR-HUB é pensado para **Linux** (testado em Ubuntu-like).  
Funciona bem também em **WSL2** no Windows, desde que os requisitos abaixo sejam atendidos.

Você vai precisar de:

- [x] **Conda** (Miniconda, Anaconda ou Mambaforge)
- [x] Acesso à internet (para instalar pacotes e, se necessário, baixar datasets do Bactopia)
- [x] Espaço em disco (vários GB se for rodar Bactopia com muitas amostras)
- [x] **Docker** (recomendado e considerado o caminho “oficial” para rodar o Bactopia via BEAR-HUB)  
- [ ] (Opcional) **Apptainer/Singularity** – para quem quiser adaptar perfis com Singularity


> 💡 O **método recomendado** para instalar o BEAR-HUB é via **conda**, usando o script `install_bear.sh`.  


---

## 🚀 2. Instalação rápida (via conda) — *recomendado*

### 2.1. Clonar o repositório

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

### 2.2. Deixar os scripts executáveis

```bash

chmod +x install_bear.sh run_bear.sh
```

### 2.3. Rodar o instalador
O script abaixo vai:

Criar (ou reaproveitar) um ambiente conda chamado bear-hub, contendo:

python 3.11

streamlit

pyyaml
(outros pacotes Python usados pelo app podem ser instalados depois via pip ou ajustando o instalador/conjunto de dependências).

Criar (ou reaproveitar) um ambiente conda chamado bactopia, contendo:

o pacote bactopia (a partir de conda-forge + bioconda), que traz Nextflow/Java e dependências do pipeline.

Detectar o prefixo real desses ambientes via conda env list.

Criar um arquivo de configuração ${HOME}/BEAR-HUB/.bear-hub.env com:

BEAR_HUB_ROOT – apontando para ~/BEAR-HUB

BACTOPIA_ENV_PREFIX – apontando para o prefixo do ambiente bactopia

NXF_CONDA_EXE – apontando para o binário do mamba, se estiver disponível
(para o Nextflow usar esse solver ao invés do conda puro).

```bash

./install_bear.sh
```

Se tudo der certo, você verá mensagens indicando:

criação ou reaproveitamento de bear-hub

criação ou reaproveitamento de bactopia

gravação de ${HOME}/BEAR-HUB/.bear-hub.env com as variáveis acima

## 📌 Observação
A primeira vez pode demorar um pouco, porque o conda precisa baixar vários pacotes de conda-forge e bioconda.

## ▶️ 3. Como rodar o BEAR-HUB
Depois da instalação:

```bash

./run_bear.sh
```

Esse script:

Descobre o diretório raiz do repositório (ROOT_DIR)

Faz source "${ROOT_DIR}/.bear-hub.env" (se existir)

Usa mamba run -n bear-hub ou conda run -n bear-hub (o que estiver disponível)

Executa o Streamlit com o arquivo principal BEAR-HUB.py

No terminal você verá algo como:

```text

  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
```
Abra o navegador e visite o endereço indicado (geralmente http://localhost:8501).

💡 Alternativa manual (se quiser):

```bash

conda activate bear-hub
# (opcional, mas o app já tenta buscar esse arquivo sozinho)
# source "${HOME}/BEAR-HUB/.bear-hub.env"
streamlit run BEAR-HUB.py
```

O próprio app tenta localizar o .bear-hub.env (via BEAR_HUB_ROOT ou ~/BEAR-HUB), então o uso de run_bear.sh é o caminho mais simples.

## 🧬 4. Organização geral do app
Ao abrir o BEAR-HUB, você verá uma tela inicial com algumas informações de ambiente:

SO

Nextflow encontrado (via PATH ou via BACTOPIA_ENV_PREFIX/bin/nextflow)

Docker/Apptainer detectados ou não

E links para as páginas:

### 4.1. Página Bactopia — Pipeline Principal
Gera um FOFN (samples.txt) automaticamente a partir de uma pasta com FASTQs/FASTAs (Pode ser selecionada uma pasta onde os fastqs estejam dentro de subpastas. É possível que os fastqs não estejam visiveis na pelo explorer do app, não se preocupe a criação do FOFN ainda funciona, em breve corrigiremos a visualização).

Detecta automaticamente o runtype:

paired-end, single-end, ont, hybrid, assembly.

Monta o comando do Bactopia (Nextflow) com as opções selecionadas.

Executa o pipeline de forma assíncrona, salvando resultados em:

```text

./bactopia_out/
```
Nessa pasta, cada amostra vai gerar um diretório próprio, por exemplo:

```text

bactopia_out/
  ├── 1228_S4_L001
  ├── 1862_S3_L001
  ├── 1236_S5_L001
  └── ...
```
Por padrão, a documentação assume que você vai rodar o pipeline com profile docker, isto é, usando containers do Bactopia para cada processo.

### 4.2. Página Ferramentas Bactopia
Usa as amostras já concluídas em bactopia_out/

Permite rodar workflows oficiais via --wf, como:

amrfinderplus

rgi

abricate

mlst

mobsuite

pangenome

mashtree

(entre outros)

Envia cada ferramenta como um job Nextflow separado, reaproveitando o output do Bactopia principal.

### 4.3. Página PORT (em desenvolvimento)
Integração com o pipeline PORT para investigações de plasmídeos e outbreaks (assemblies long/short read, híbridos, etc.).

A interface segue o mesmo padrão: seleção de assemblies de entrada + parâmetros essenciais.

## 📁 5. Pastas padrão
Por padrão, o BEAR-HUB usa:

./BEAR-HUB/bactopia_out/ — saída principal do Bactopia e das ferramentas (--wf)

Outras pastas relacionadas ao Bactopia/Nextflow podem aparecer, como:

work/ (trabalho interno do Nextflow)

bactopia_out/bactopia-runs/ (metadata de runs)

.nextflow/ (cache e histórico) – pode existir tanto em HOME quanto dentro da pasta de saída, dependendo da configuração

Pastas externas que você configurar (como BEAR_DATA, BEAR_OUT etc.) podem ser usadas se você personalizar variáveis de ambiente e perfis.

Você pode ajustar caminhos dentro da interface ou, se desejar fine-tuning, mexer na configuração do Bactopia (profiles, datasets, etc.) fora do app.

## 📦 6. Bactopia, datasets e containers
O BEAR-HUB não instala datasets do Bactopia automaticamente — ele só chama o comando nextflow run bactopia/bactopia com os parâmetros que você escolhe.

Na primeira execução de um pipeline, o Bactopia pode:

Baixar datasets oficiais (vários GB), ou

Pedir um caminho de datasets já existentes

Para detalhes, consulte a documentação oficial do Bactopia.

Sobre containers:

O Bactopia normalmente é executado via Docker ou Apptainer/Singularity.

A interface do BEAR-HUB foi pensada para uso com containers:

-profile docker (caminho recomendado/testado)

Mesmo que o app em si não esteja rodando em Docker,
as ferramentas de bioinformática podem ser executadas em containers via Bactopia/Nextflow.

⚠️ O uso de -profile standard (conda puro) pode voltar a depender de criação de ambientes via conda/mamba dentro do pipeline
e não é coberto pelo install_bear.sh. Se você quiser usar este modo, considere-o um cenário avançado.

## 🔄 7. Como atualizar o BEAR-HUB (a partir do GitHub)

Se você instalou o BEAR-HUB clonando este repositório:

```bash
cd /caminho/para/BEAR-HUB    # ex.: cd ~/BEAR-HUB
git pull origin main         
```

Isso vai:

baixar as alterações mais recentes do repositório (código do app, scripts, etc.)

manter seus ambientes conda já criados (bear-hub e bactopia)

Na maioria dos casos não é necessário recriar os ambientes.
Mas se o README ou o install_bear.sh tiverem mudado dependências importantes, você pode rodar de novo:

```bash

cd /caminho/para/BEAR-HUB
chmod +x install_bear.sh run_bear.sh
./install_bear.sh
```
💡 O install_bear.sh é idempotente: ele só cria os ambientes conda se ainda não existirem
e apenas atualiza o arquivo .bear-hub.env se necessário.

## 🧹 8. Como desinstalar o BEAR-HUB (remoção completa)
Se quiser remover o BEAR-HUB da sua máquina, os passos são:

### 4.1. Parar o app
Se o app estiver rodando (via run_bear.sh ou streamlit run), pare o processo
(ctrl+C no terminal ou feche o terminal/janela).

### 4.2. Remover ambientes conda
Remova os ambientes criados pelo instalador:

```bash

conda remove -n bear-hub --all #ou mamba remove -n bear-hub --all
conda remove -n bactopia --all #ou mamba remove -n bactopia
```
Confirme quando o conda perguntar.

### 4.3. Excluir pastas do BEAR-HUB e saídas do Bactopia
Pasta do repositório (código do app):

```bash
rm -rf /caminho/para/BEAR-HUB   # ex.: rm -rf ~/BEAR-HUB
```
Pasta de saída padrão do Bactopia (se quiser liberar espaço):

```bash
rm -rf ~/BEAR-HUB/bactopia_out
```
⚠️ Isso apaga todos os resultados de execução do Bactopia (assemblies, relatórios, etc.).
Faça backup antes se precisar desses arquivos.


❓ 9. Problemas comuns
conda: command not found

→ Instale Miniconda/Mambaforge, feche e reabra o terminal, depois rode novamente:

```bash

./install_bear.sh
Streamlit abre mas não encontro as páginas
```

→ Verifique se a estrutura está assim:

```text

BEAR-HUB/
  BEAR-HUB.py
  pages/
    BACTOPIA.py
    BACTOPIA-TOOLS.py
    PORT.py
    TEST.py
```
(as páginas precisam estar dentro da pasta pages/)

Bactopia reclamando de datasets / profiles

→ Ajuste as configurações do Bactopia (datasets/profile) diretamente no seu ambiente,
depois volte ao BEAR-HUB e rode novamente com o profile adequado (recomendado: docker).

Docker não encontrado / permissão negada

→ Verifique se o comando docker info funciona para o seu usuário.
Em muitas distros, é necessário adicionar o usuário ao grupo docker e relogar:

```bash

sudo usermod -aG docker "$USER"
# depois faça logout/login ou reinicie a sessão
```
## 🤝 10. Contribuição
Sugestões, issues e PRs são bem-vindos!
O foco do BEAR-HUB é ser:

🧪 Prático para rotina de laboratório

🧬 Opinativo, mas flexível o suficiente para diferentes fluxos

🐻 Amigável para quem quer usar Bactopia/Nextflow sem decorar todos os comandos

## 📜 11. Licença
Este projeto é licenciado sob os termos da MIT License.

Copyright (c) 2025 João Pedro Stepan Wagner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
