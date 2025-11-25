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
- [ ] (Opcional, mas recomendado para Bactopia)  
      **Docker** ou **Apptainer/Singularity** como engine de container

> 💡 Por enquanto o **método recomendado e suportado oficialmente** é a instalação **local via conda**, usando o script `install_bear.sh`.  
> O modo via Docker da aplicação inteira foi descontinuado.

---

## 🚀 2. Instalação rápida (via conda) — *recomendado*

### 2.1. Clonar o repositório

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

2.2. Deixar os scripts executáveis

```bash
chmod +x install_bear.sh run_bear.sh
```

2.3. Rodar o instalador
O script abaixo vai:

Criar (ou reaproveitar) o ambiente conda chamado bear-hub

Instalar:

python (3.11)

openjdk=11

nextflow

bactopia

git e pip

Instalar as dependências Python do app via requirements.txt (Streamlit etc.)

```bash
./install_bear.sh
```

Se tudo der certo, você verá algo como:

```text
OK! Ambiente 'bear-hub' pronto.
Para rodar o app, use:  ./run_bear.sh
```

📌 Observação
A primeira vez pode demorar um pouco, porque o conda precisa baixar vários pacotes de bioconda/conda-forge.

▶️ 3. Como rodar o BEAR-HUB
Depois da instalação:

```bash
./run_bear.sh
```

Esse script:

Usa o ambiente conda bear-hub

Executa o Streamlit com o arquivo principal BEAR-HUB.py

No terminal você verá algo como:

```text
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
Abra o navegador e visite o endereço indicado (geralmente http://localhost:8501).
```

💡 Alternativa manual (se quiser):

```bash
conda activate bear-hub
streamlit run BEAR-HUB.py
```

🧬 4. Organização geral do app
Ao abrir o BEAR-HUB, você verá uma tela inicial com algumas informações de ambiente
(SO, Nextflow, Docker/Apptainer detectado ou não) e links para as páginas:

4.1. Página Bactopia — Pipeline Principal
Gera um FOFN automaticamente a partir de uma pasta com FASTQs

Monta o comando do Bactopia (Nextflow) com as opções selecionadas

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

4.2. Página Ferramentas Bactopia
Usa as amostras já concluídas em bactopia_out/

Permite rodar workflows oficiais via --wf, como:

amrfinderplus

rgi

abricate

mlst

mobsuite

pangenome

mashtree

Envia cada ferramenta como um job Nextflow separado, reaproveitando o output do Bactopia principal.

4.3. Página PORT (em desenvolvimento)
Integração com o pipeline PORT para investigações de plasmídeos e outbreaks (assemblies long/short read, híbridos, etc.)

A interface segue o mesmo padrão: seleção de assemblies de entrada + parâmetros essenciais.

📁 5. Pastas padrão
Por padrão, o BEAR-HUB usa:

./bactopia_out/ — saída principal do Bactopia e das ferramentas (--wf)

Outras pastas relacionadas ao Bactopia/Nextflow podem aparecer, como:

work/ (trabalho interno do Nextflow)

bactopia_out/bactopia-runs/ (metadata de runs)

Pastas externas que você configurar, como BEAR_DATA / BEAR_OUT, se estiver usando perfis personalizados

Você pode ajustar caminhos dentro da interface ou, se desejar fine-tuning, mexer na configuração do Bactopia (profiles, datasets, etc.) fora do app.

📦 6. Bactopia, datasets e containers
O BEAR-HUB não instala datasets do Bactopia automaticamente
— ele só chama o comando bactopia com os parâmetros que você escolhe.

Na primeira execução de um pipeline, o Bactopia pode:

Baixar datasets oficiais (vários GB), OU

Pedir um caminho de datasets já existentes

Para detalhes, consulte a documentação oficial do Bactopia.

Sobre containers:

O Bactopia normalmente é executado via Docker ou Apptainer/Singularity

O BEAR-HUB apenas verifica se algum engine está disponível no PATH e deixa o Nextflow/Bactopia cuidarem do resto

👉 Mesmo que o app em si não esteja rodando em Docker,
as ferramentas de bioinformática podem sim ser executadas em containers via Bactopia/Nextflow.

❓ 7. Problemas comuns
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
depois volte ao BEAR-HUB e rode novamente.

🤝 8. Contribuição
Sugestões, issues e PRs são bem-vindos!
O foco do BEAR-HUB é ser:

🧪 Prático para rotina de laboratório

🧬 Opinativo, mas flexível o suficiente para diferentes fluxos

🐻 Amigável para quem quer usar Bactopia/Nextflow sem decorar todos os comandos

📜 9. Licença
## Licença

Este projeto é licenciado sob os termos da **MIT License**.

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
