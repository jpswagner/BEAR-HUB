<p align="center">
<img width="480" height="480" alt="Gemini_Generated_Image_dr7x8bdr7x8bdr7x" src="https://github.com/user-attachments/assets/6d23dc4b-fc4d-4fa7-9b2a-e55adb623598" />
</p>

# BEAR-HUB (Bacterial Epidemiology & AMR Reporter - HUB) — EM DESENVOLVIMENTO

Interface simples e opinativa em **Streamlit** para orquestrar ferramentas de bioinformática:

- **Bactopia** (pipeline e Tools) via **Nextflow**
- **PORT** (assemblies Nanopore/Illumina) via Nextflow

---

# Guia de Instalação — BEAR-HUB (via Docker)

O BEAR-HUB foi pensado para rodar **inteiro dentro de um container Docker**, sem precisar configurar Python, Nextflow ou Bactopia diretamente no host.

A imagem Docker contém:

- Python + Streamlit + dependências do app  
- Nextflow + Java  
- Bactopia  
- (Opcional) PORT clonado dentro da imagem  

---

## 1. Pré-requisitos

No host, você precisa ter:

- **Linux x86_64**  
- **Git**
- **Docker** instalado e funcionando  
  - Linux (recomendado)  
  - ou Windows/macOS com **Docker Desktop**

Verifique se o Docker está disponível:

```bash
docker --version
```
Se der erro, instale e/ou configure o Docker antes de continuar.

💡 Se quiser rodar docker sem sudo, adicione seu usuário ao grupo docker:


```bash
sudo usermod -aG docker "$USER"
newgrp docker   # ou faça logout/login
```
2. Clonar o repositório

```bash
git clone https://github.com/jpswagner/BEAR-HUB.git
cd BEAR-HUB
```

3. Primeira execução (build + subir o app)
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

text

== BEAR-HUB ==
Dados de entrada (host): /home/usuario/BEAR_DATA
Resultados saída (host): /home/usuario/BEAR_OUT

Abrindo em: http://localhost:8501
Na primeira vez, o Docker vai baixar a imagem base e instalar as dependências (leva alguns minutos).

4. Acessar a interface web
Com o container rodando, abra o navegador em:

text

http://localhost:8501
A partir daí você pode:

Selecionar FASTQs/assemblies na pasta mapeada (ver seção abaixo).

Gerar o FOFN (samples.txt) a partir dos FASTQs/FASTA.

Rodar o Bactopia a partir da interface.

Acompanhar o log do Nextflow em tempo real.

Ver os resultados no diretório de saída mapeado.

5. Diretórios de dados e resultados
O script bear-hub.sh monta, por padrão, os seguintes volumes:


```bash
-v "$BEAR_DATA":/dados \
-v "$BEAR_OUT":/bactopia_out \
-v /:/hostfs:ro
```

Ou seja, dentro do container você terá:

/dados → diretório de entradas

por padrão, mapeado para ~/BEAR_DATA no host

/bactopia_out → diretório de saídas

por padrão, mapeado para ~/BEAR_OUT no host

/hostfs → raiz do host em modo somente leitura (uso avançado)

Fluxo recomendado (mais simples)
No host, crie (se ainda não existirem):


```bash
mkdir -p ~/BEAR_DATA ~/BEAR_OUT
```

Copie ou mova seus FASTQs/assemblies para ~/BEAR_DATA:

```bash
cp /mnt/HD/joao/031125_bactopia/*.fastq.gz ~/BEAR_DATA/
```

Rode o BEAR-HUB:


```bash
./bear-hub.sh
```

No app, use /dados como “Pasta base de FASTQs/FASTAs” no gerador de FOFN.

6. Acesso do Docker aos arquivos do host

6.1. Por que algumas pastas aparecem vazias?
Mesmo com /hostfs montado, algumas pastas podem aparecer vazias ou inacessíveis no explorador de arquivos do app. Isso normalmente acontece porque:

O container roda como um usuário não-root (mambauser).

O Docker respeita as permissões do host:

Se o seu usuário no host não consegue ler aquela pasta, o container também não vai conseguir.

Se o disco foi montado com permissões restritivas, o container pode “ver” o diretório mas não listar arquivos.

6.2. Garantindo que o BEAR-HUB consiga ver seus dados
Há duas formas principais de trabalhar:

🔹 Opção A — Usar apenas BEAR_DATA (recomendado)
Coloque seus dados de entrada dentro de BEAR_DATA (por padrão ~/BEAR_DATA):


```bash
mkdir -p ~/BEAR_DATA
cp /mnt/HD/joao/031125_bactopia/*.fastq.gz ~/BEAR_DATA/
./bear-hub.sh
```

No app, use /dados como base para o FOFN.

🔹 Opção B — Apontar BEAR_DATA diretamente para o disco/pasta onde já estão os dados
Se seus dados já estão, por exemplo, em:


/mnt/HD/joao/031125_bactopia


você pode rodar assim:


```bash
BEAR_DATA=/mnt/HD/joao/031125_bactopia \
BEAR_OUT=$HOME/BEAR_OUT \
./bear-hub.sh
```
Dentro do container isso vira:

/dados -> /mnt/HD/joao/031125_bactopia  (no host)
No app, basta escolher /dados (ou navegar a partir dele) como “Pasta base de FASTQs/FASTAs”.

🔹 Opção C — Usar /hostfs (avançado)
O diretório /hostfs é a raiz do host montada em modo somente leitura.
Você pode navegar por ele como se estivesse na raiz:

/hostfs/mnt/HD/joao/...

/hostfs/home/usuario/...

Essa abordagem exige que as permissões no host permitam leitura para o usuário que o Docker está usando.

6.3. Ajustando permissões no host
Se uma pasta aparece vazia no app, mas você vê arquivos via ls no host, pode ser questão de permissões para outros usuários/grupos.

Uma solução “larga” (use com cuidado) é:


```bash
sudo chmod -R a+rX /mnt/HD/joao
```

Isso garante leitura e permissão de entrar nas pastas para todos os usuários.
Se quiser algo mais restrito, use grupos (ex.: criar um grupo que tem acesso ao HD e adicionar o usuário que roda o Docker a esse grupo).

7. Personalizar diretórios de entrada/saída
Você pode mudar os diretórios de entrada (BEAR_DATA) e saída (BEAR_OUT) no host sem editar o script, apenas usando variáveis de ambiente:

```bash

BEAR_DATA=/caminho/para/meus_fastqs \
BEAR_OUT=/caminho/para/meus_resultados \
./bear-hub.sh
```
BEAR_DATA → mapeado para /dados dentro do container.

BEAR_OUT → mapeado para /bactopia_out dentro do container.

8. Atualizar o BEAR-HUB
Para atualizar o app para a última versão do repositório:


```bash
cd BEAR-HUB
git pull origin main
./bear-hub.sh
```
Se o Dockerfile tiver mudado, você pode forçar um rebuild da imagem:


```bash
./bear-hub.sh --rebuild
```

9. Problemas comuns
9.1. “Docker não encontrado no PATH”
Mensagem típica:


Erro: 'docker' não encontrado no PATH.
Instale Docker antes de rodar o BEAR-HUB.
Instale o Docker (ou Docker Desktop).

Verifique com docker --version.

Se estiver usando Linux com sudo, teste sudo docker ps.

9.2. Pastas vazias no explorador do app
Verifique se você consegue listar os arquivos no host (ls /mnt/HD/joao/...).

Use a opção B (apontar BEAR_DATA para a pasta real dos dados).

Ajuste permissões com chmod ou grupos, se necessário.

Qualquer contribuição, issue ou sugestão de melhoria é bem-vinda no repositório 🙂