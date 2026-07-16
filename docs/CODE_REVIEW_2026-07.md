# BEAR-HUB — Revisão técnica de arquitetura e código

**Escopo:** camada de aplicação (orquestração Reflex + Nextflow/Docker, UI/UX, infraestrutura de software).
**Fora de escopo:** lógica científica/bioinformática do Bactopia / MERLIN / Bactopia Tools.
**Base analisada:** branch `main`, commit `f309733`, mais 3 mudanças não commitadas em `shell.py`, `system.py`, `rxconfig.py`.
**Data:** 2026-07-16.

---

## 0. Resumo executivo

BEAR-HUB é um wrapper Reflex bem organizado sobre o Bactopia. A separação de módulos é limpa
(`core/` lógica pura → testável, `pages/` view, `components/` chrome reutilizável, `data/` catálogo),
os construtores de comando usam `shlex.quote` de forma disciplinada, e há detalhes de produto maduros
(pré-check do daemon Docker, parser de progresso/falha, presets, FOFN editável, verificador de update).

Os problemas mais sérios **não estão na UI — estão no ciclo de vida dos processos**:

1. **Parar um run não mata o Nextflow/Docker** — o `stop()` sinaliza só o shell `bash`, deixando a árvore
   `java`/containers viva (órfãos).
2. **Nenhum estado de processo é persistido** — após um restart do backend o app perde todo handle dos
   runs (que sobrevivem reparentados para o init). Isso é a causa-raiz dos "runs órfãos".
3. **O streaming de log ao vivo é O(n²)** — cada linha re-serializa a lista inteira de 1500 linhas e
   re-parseia todo o log (computed var `_prog`), o que degrada CPU/rede em runs longos.
4. **O frontend/backend não têm gestão de ciclo de vida** — a manifestação concreta é o **frontend
   órfão de 34 dias (PID 2492685)** e o **`reflex_live.log` de ~19 GB**, além da mudança de porta
   `8200→8201` (workaround de porta presa) ainda não commitada.

Nada disso é difícil de corrigir e a maior parte são *quick wins* de baixo risco.

---

## 1. Backend / Arquitetura Reflex

### 1.1 Organização de módulos — **boa**
- `bearhub/core/` concentra a lógica sem dependência de Reflex (`fofn`, `runner`, `history`, `progress`,
  `bactopia`, `system`, `versions`, `presets`) — trivialmente testável e o suite cobre boa parte.
- `pages/` só monta view; `components/wizard.py` e `components/shell.py` isolam o chrome; `data/catalog.py`
  é a fonte única do catálogo de tools. Essa camada está saudável e sustentável.
- **Dívida:** `state.py` tem **1196 linhas** e mistura 5 states + todos os construtores de comando do
  pipeline principal (`_main_cmd`, `_assembler_flags`, `_typing_flags`, `_fastp_opts`, `_json_params`).
  Esses builders são lógica pura e deveriam viver em `core/` (ex.: `core/bactopia_cmd.py`), deixando
  `state.py` só com estado/handlers. Facilita teste e leitura.

### 1.2 State management
- `WizardMixin` como base compartilhada (nav de passos, picker de diretório, samples, params gerais,
  log/status do runner) é um bom padrão e evita repetição entre `BactopiaState`/`ToolsState`/`MerlinState`.
- **Re-render desnecessário (alto impacto):** `@rx.var _prog` chama `progress.parse(self.log)` sobre **todas**
  as linhas do log, e dele dependem `prog_stages`, `prog_current`, `prog_summary`, `has_error`, `err_*`.
  Como `state.log` muda a cada linha durante o streaming, o log inteiro é re-parseado a cada linha
  ([state.py:237-270](../bearhub_rx/bearhub/state.py#L237-L270)). Ver §1.4.
- **Duplicação:** `run` / `stop_run` / `_build` / `preview` são praticamente idênticos em `ToolsState`,
  `MerlinState` e `BactopiaState`. Dá para extrair um mixin `RunnableMixin.run(ns, page, build_fn)`.
- `set_threads`/`set_memory` normalizam listas do slider — ok, mas repetido; centralizar.

### 1.3 Orquestração de processos — **o ponto mais crítico**

Arquivo: [`core/runner.py`](../bearhub_rx/bearhub/core/runner.py).

**H1 — `stop()` deixa Nextflow/Docker órfãos.**
O run é disparado com `asyncio.create_subprocess_exec("bash","-c",cmd)` **sem sessão/grupo próprio**
([runner.py:193-199](../bearhub_rx/bearhub/core/runner.py#L193-L199)). Como o comando é composto
(`cd <dir> && nextflow ...`, ou `echo banner ; cmd ; ...`), o bash **não** faz `exec` — ele fork-a o
Nextflow (`java`) como filho, que por sua vez sobe a JVM e containers Docker. O `stop()` chama
`proc.terminate()`, que envia **SIGTERM só para o `bash`** ([runner.py:246-262](../bearhub_rx/bearhub/core/runner.py#L246-L262)).
O bash morre, o `java` fica órfão e os containers seguem rodando.

**Correção** (colocar o run no próprio grupo e sinalizar o grupo inteiro):

```python
# runner.stream()
proc = await asyncio.create_subprocess_exec(
    "bash", "-c", cmd,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd,
    env={**os.environ, "PYTHONUNBUFFERED": "1", "NXF_ANSI_LOG": "false"},
    start_new_session=True,          # <-- novo grupo/sessão: isola a árvore do run
)

async def _terminate(proc):
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):  # graceful → forçado
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=8)
            return
        except asyncio.TimeoutError:
            continue
```
SIGINT primeiro deixa o Nextflow rodar seu shutdown (mata os containers que ele criou); SIGKILL é a
garantia. Isso resolve `stop()`, `stop_run_id()` e o cancelamento em massa.

**H2 — Nenhum PID/PGID é persistido → órfãos após restart.**
`_PROCS` e `_PROCS_BY_ID` são dicts **em memória** ([runner.py:23-24](../bearhub_rx/bearhub/core/runner.py#L23-L24)).
Se o backend reinicia (crash, update, `reflex` hot-reload), esses dicts zeram, mas os processos Nextflow
já lançados são reparentados para o init e **continuam vivos** — sem nenhum handle para monitorar ou parar.
`history.cancel_stale()` só troca o rótulo do registro para `interrupted` **sem matar nada**
([history.py:109-123](../bearhub_rx/bearhub/core/history.py#L109-L123)): a UI mente ("interrompido")
enquanto o pipeline segue. **Essa é a origem do troubleshooting de "runs órfãos".**

**Correção:** gravar `pid` e `pgid` no registro de history quando o processo sobe; no boot, reconciliar:
```python
# em stream(), logo após criar o proc:
_hist.set_proc_info(run_id, pid=proc.pid, pgid=os.getpgid(proc.pid))

# core/history.py — no startup (RunsState.load):
def reconcile_orphans():
    for r in load_all():
        if r["status"] != "running":
            continue
        pid = r.get("pid")
        if pid and _pid_alive(pid):
            # ainda vivo e reparentado: registra para permitir stop pela UI
            runner.adopt(r["id"], pid, r.get("pgid"))
        else:
            finish_record(r["id"], exit_code=-1)  # de fato terminou
```
Com o PGID salvo, o botão *Stop* na página Runs volta a funcionar mesmo depois de um restart, e o
`cancel_stale` passa a matar de verdade (`os.killpg(pgid, SIGTERM)`) em vez de só relabelar.

**H2b — Sem timeout de parede.** Um Nextflow travado roda para sempre. Adicionar um teto opcional
(`BEAR_HUB_RUN_TIMEOUT`) e/ou um "watchdog" que mata runs `running` com `started` além do limite.

### 1.4 Streaming de logs em tempo real — **O(n²)**

Em [runner.py:207-227](../bearhub_rx/bearhub/core/runner.py#L207-L227), a cada `\n` recebido:
```python
async with state:
    state.log = (state.log + lines)[-MAX_LOG_LINES:]   # nova lista de até 1500 itens
```
Cada atribuição faz o Reflex serializar/diff a lista inteira e empurrar pelo websocket, **e** invalida
o computed var `_prog`, que re-parseia até 1500 linhas — **por linha**. Num run com dezenas de milhares
de linhas isso é dezenas de milhares de re-serializações + re-parses completos. É o principal gargalo de
performance e casa com a lentidão observada.

**Correção — coalescer flushes** (throttle temporal + em lote):
```python
BUF_LINES, BUF_MS = 40, 300
pending, last_flush = [], time.monotonic()

async def flush(force=False):
    nonlocal pending, last_flush
    if not pending: return
    if force or len(pending) >= BUF_LINES or (time.monotonic()-last_flush)*1000 >= BUF_MS:
        chunk, pending = pending, []
        async with state:
            state.log = (state.log + chunk)[-MAX_LOG_LINES:]
        last_flush = time.monotonic()
```
E tornar o parser de progresso incremental (guardar o último índice parseado em vez de reprocessar tudo),
ou derivá-lo só quando o run termina + a cada N segundos, não a cada linha. O log em disco
(`log_fh`) continua sendo a fonte completa/autoritativa.

### 1.5 Persistência (history.jsonl) — reescrita total + corrida

- `append_record` e `finish_record` fazem **read-modify-write do arquivo inteiro** a cada chamada
  ([history.py:54-68](../bearhub_rx/bearhub/core/history.py#L54-L68), [93-106](../bearhub_rx/bearhub/core/history.py#L93-L106)),
  e `RunsState.monitor` faz `load_all()` (parse do arquivo todo) **a cada 2 s**.
- **Race condition:** sem lock. O app suporta runs paralelos (registro por `run_id`) e, se o Granian
  subir mais de 1 worker, dois processos reescrevendo o mesmo `.jsonl` perdem updates. Mesmo com 1 worker,
  um `finish_record` e um save do editor de FOFN podem interleavar entre `await`s.
- **Correção:** `filelock`/`fcntl.flock` em volta de leitura+escrita, **ou** migrar para SQLite (WAL cuida
  de concorrência e ainda permite query por status sem reparsear tudo). SQLite é o alvo natural aqui.

### 1.6 Tratamento de erros / falhas silenciosas
- `get_bactopia_version` cai para `"4.0.0"` hardcoded em qualquer falha ([system.py:42-75](../bearhub_rx/bearhub/core/system.py#L42-L75)) — pode pinar a versão errada silenciosamente.
- `versions._run` engole `Exception → ""`; `stream()` captura `Exception` e só anexa uma linha ao log,
  seguindo para "success/failed" pelo `rc` — uma falha de leitura de stream vira "sucesso" enganoso.
- Nenhum uso de `logging`; erros somem. Adotar um logger com nível configurável ajudaria diagnóstico
  (ver §3, a tabela de troubleshooting do README é sintoma disso).

### 1.7 Validação de inputs / segurança de comando — **adequada, com ressalvas**
- Todos os args passam por `shlex.quote`; campos livres (`extra_params`, `fastp_extra`, tool `.extra`)
  vão por `shlex.split` e são requotados → **sem injeção de shell**. Paths do picker são read-only e
  resolvidos por `safe_dir`. Nomes de preset são chaves de dict JSON, não paths → **sem traversal**.
- Ressalva (aceitável p/ ferramenta de lab single-user, mas documente): os campos livres permitem
  qualquer flag do Nextflow (`-c arquivo.config`, `-with-docker`, etc.). Não é injeção de shell, mas é
  execução arbitrária no contexto do Nextflow. Ok num lab confiável; explicite no help.
- **M3 — duplo aspeamento:** `_fastp_opts` monta uma string já com aspas internas
  (`-a 'ADAPTER'`) que depois é requotada inteira como um único arg em `_main_cmd`
  ([state.py:597-635](../bearhub_rx/bearhub/state.py#L597-L635)). Não é falha de segurança, mas as aspas
  internas podem chegar literais ao fastp. Verificar o round-trip real.

### 1.8 Configuração (`~/.bear-hub/config.env`)
- Gerada pelo installer; carregada por `bootstrap_env()` com `os.environ.setdefault` (não sobrescreve o
  que já está no ambiente) e regex simples de `export VAR=...` ([system.py:157-177](../bearhub_rx/bearhub/core/system.py#L157-L177)). Clara e sem segredos sensíveis.
- **L1:** o docstring de `rxconfig.py` diz "backend 8200" mas o valor (não commitado) virou `8201`.
  Alinhar; e considerar tornar as portas configuráveis por env (`BEAR_HUB_FRONTEND_PORT`/`_BACKEND_PORT`)
  para evitar o workaround manual de porta presa.

### 1.9 Testes automatizados — **bons para lógica pura, ausentes para processo/UI**
- `tests/` cobre bem: `fofn` (classificação de runtype), construtor de comando (`_main_cmd`,
  `_assembler_flags`, `_fastp_opts`), `history` (persistência/format), `RunsState._enrich`.
- **Lacunas:** zero cobertura de `runner.stream/stop` (o exato ponto crítico H1/H2), event handlers de
  state, e páginas. Os testes são **scripts standalone** (imprimem ✅/❌, `sys.exit`), **não pytest**, e
  **não há CI** — ninguém garante que rodam a cada push. Migrar para `pytest`, adicionar testes de
  `runner` (com um comando fake tipo `sleep`/`yes`), e um workflow GitHub Actions.

### 1.10 Dependências
- Reflex pinado exato (`0.9.3`) — correto, dado que quebra entre patches. Bactopia pinado 4.0.0.
  Mistura conda+pip é gerenciada pelo installer de forma idempotente.
- **Risco:** a versão do Reflex "sabe demais" sobre o layout do `.web` (o `update_bear.sh` apaga `.web`
  para forçar rebuild). Prender a versão é a mitigação certa; documentar o procedimento de bump.

---

## 2. Frontend / UX

### 2.1 Fluxo principal
Wizard por passos (`step_indicator` clicável) é a escolha certa. Fricções:

- **Passo 1 (Input & FOFN) sobrecarregado:** outdir + base folder + species + genome size + 5 checkboxes
  + botão scan + badge + issues + editor de sample sheet + card de QC thresholds, tudo empilhado
  ([pages/bactopia.py:268-358](../bearhub_rx/bearhub/pages/bactopia.py#L268-L358)). É o passo com maior
  carga cognitiva. Ver wireframe §5.
- **Preview do comando** só aparece no último passo. Um preview *sempre visível* (rail lateral) daria
  feedback contínuo do efeito de cada parâmetro.
- **Discovery síncrono no on_load:** `init_outdir → scan → discover_samples` roda `iterdir()`+stat no
  handler ([state.py:95-107](../bearhub_rx/bearhub/state.py#L95-L107)); em diretório grande trava a página.
  Tornar background (`@rx.event(background=True)`) com spinner.

### 2.2 Consistência visual — **boa, com um furo de idioma**
- Paleta teal coesa, heros com gradiente, cards uniformes, badges de status com cor semântica. Sólido.
- **L5 — idioma misto:** todo o app é em inglês, mas o diálogo de shutdown e vários toasts/installer
  estão em **português** ([components/shell.py:108-126](../bearhub_rx/bearhub/components/shell.py#L108-L126)).
  Escolher um idioma (ou i18n) e padronizar.

### 2.3 Feedback ao usuário
- **Bom:** toasts de sucesso/erro, badge de status colorido, `progress_strip`, `failure_panel` com processo
  + workdir para inspecionar, banner de daemon Docker off, notificação desktop ao concluir.
- **Faltando confirmação em ação destrutiva:** *Stop run* dispara direto, sem confirmar
  ([components/wizard.py:238-246](../bearhub_rx/bearhub/components/wizard.py#L238-L246)) — interromper um
  pipeline de horas merece um `alert_dialog` como o do shutdown. `remove_fofn_row` também remove sem
  confirmar.
- **Onboarding do 1º launch (1–2 min compilando):** hoje o usuário fica no escuro. Uma tela/*toast* de
  "primeira execução: compilando o frontend, ~2 min" evitaria a percepção de travamento.

### 2.4 Hierarquia em telas densas
- Passo de parâmetros de tools e o passo Typing têm muitos campos lado a lado. Agrupar em accordions
  (já usado no card de QC thresholds) e mostrar só o painel do tool selecionado (já feito em
  `_detailed_panel`) — estender esse padrão.

### 2.5 Responsividade e acessibilidade
- Sidebar colapsa para rail de ícones em telas estreitas (bom); grids usam `wrap`.
- **Acessibilidade:** o checkbox do card de tool usa `pointerEvents:none` e o clique é no card
  ([pages/tools.py:110-135](../bearhub_rx/bearhub/pages/tools.py#L110-L135)) — não é focável/operável por
  teclado. Badges "chip" de sample são clicáveis mas não são `button`/checkbox (sem foco/ARIA). O
  `dir_picker` navega por clique sem suporte a teclado. Vale um passe de labels/roles/foco.
- Contraste: textos `--gray-9`/`--gray-10` sobre fundo claro ficam no limite AA em telas pequenas.

---

## 3. Instalação / Operação

- `install_bear.sh` é robusto e idempotente: instala conda (Miniforge) se faltar, cria os 2 envs, escreve
  `config.env`, desliga telemetria do Reflex, e tem o **Step 6 de verificação** (checa `reflex` CLI,
  Nextflow, Bactopia, daemon Docker) com sumário OK/WARN/FAIL. Bom.
- **Lacuna do Step 6:** não verifica **portas livres (3200/8200)** nem se há **instância anterior rodando**
  — justamente o que gerou o órfão e o workaround de porta. Adicionar checagem de porta e um smoke test
  "sobe o app por Nx segundos e faz um GET em /".
- **Prevenir em vez de documentar:** vários itens da tabela de troubleshooting do README são preveníveis:
  - *"run órfão após restart"* → §1.3 (H2, persistir PID/PGID + reconciliar no boot).
  - *"porta em uso"* → `run.sh`/installer detecta e oferece matar a instância anterior.
  - *"disco enchendo / log gigante"* → não redirecionar `reflex run` para um arquivo ilimitado; usar
    rotação (`logrotate`/`RotatingFileHandler`) ou `run.sh` truncando no start.
- `update_bear.sh`: sólido (stash → ff-only pull → reinstala idempotente → limpa `.web`). **Furo:** não
  **para o app rodando** antes de trocar código/porta, então um app antigo pode continuar segurando a
  porta e servindo código velho. Adicionar um passo de "stop" (ver §6/roadmap).
- `uninstall_bear.sh`: presente; conferir se remove `~/.bear-hub`, `~/.bactopia_ui_local` e os envs.

---

## 4. Tabela priorizada de problemas

| # | Área | Problema | Sev. | Esforço | Arquivo(s) |
|---|------|----------|------|---------|-----------|
| H1 | Processos | `stop()` mata só o `bash`; Nextflow/`java`/containers ficam órfãos | **Crítico** | ~0,5 d | `core/runner.py:193,246-284` |
| H2 | Processos | PID/PGID não persistidos → sem handle após restart; `cancel_stale` só relabela | **Crítico** | ~1 d | `core/runner.py:23-24`, `core/history.py:109-123` |
| H3 | Performance | Log ao vivo O(n²): re-serializa lista + re-parseia `_prog` por linha | **Alto** | ~0,5 d | `core/runner.py:207-227`, `state.py:237-270` |
| H4 | Operação | Sem gestão de ciclo de vida (órfão de 34 d + log 19 GB + porta presa) | **Alto** | ~0,5 d | `bearhub_rx/run.sh`, `update_bear.sh` |
| M1 | Persistência | JSONL reescrito por inteiro + race sem lock | Médio | ~1 d | `core/history.py` |
| M2 | Performance | `monitor` faz `load_all()`+tail completo a cada 2 s | Médio | ~0,5 d | `state.py:1119-1151` |
| M3 | Correção | Duplo aspeamento de `--fastp_opts` | Médio | ~0,25 d | `state.py:597-635,842-872` |
| M4 | Robustez | Falhas silenciosas (versão hardcoded, `Exception→""`, sem logging) | Médio | ~0,5 d | `core/system.py`, `core/versions.py` |
| M5 | UX/Perf | `discover_samples` síncrono no `on_load` trava página | Médio | ~0,25 d | `state.py:95-107` |
| M6 | Arquitetura | `run/stop/_build/preview` duplicados em 3 states; builders em `state.py` | Médio | ~1 d | `state.py` |
| L1 | Config | Docstring 8200 vs config 8201; portas não configuráveis | Baixo | ~0,1 d | `rxconfig.py` |
| L2 | UX | *Stop run* / remover sample sem confirmação | Baixo | ~0,25 d | `components/wizard.py`, `pages/bactopia.py` |
| L3 | Qualidade | Testes não-pytest, sem CI, sem cobertura de `runner` | Baixo | ~0,5 d | `bearhub_rx/tests/` |
| L4 | UX | Idioma misto PT/EN | Baixo | ~0,25 d | `components/shell.py` etc. |
| L5 | A11y | Card de tool não focável; chips sem role; picker sem teclado | Baixo | ~0,5 d | `pages/tools.py`, `components/wizard.py` |
| L6 | Limpeza | `merge_multi` ignorado em `_pick`; `import importlib` desnecessário; `write_include_file` duplicado | Baixo | ~0,25 d | `core/fofn.py:114-121`, `state.py:655-656` |

**Quick wins (< 1 dia cada):** H1, H3, H4, M3, M5, L1, L2, L6.
**Estruturais (médio prazo):** H2 (persistir/reconciliar PIDs), M1 (SQLite + lock), M6 (extrair builders +
`RunnableMixin`), L3 (pytest + CI), L5 (passe de acessibilidade).

---

## 5. Proposta visual (para recriar no Claude Design)

### 5.1 Tela "New Analysis" com rail de resumo persistente
Objetivo: aliviar o passo 1 e dar feedback contínuo.

```
┌───────────────────────────────────────────────┬───────────────────────┐
│  ● Input  ─ ○ Cleaning ─ ○ Assembler ─ …       │  RESUMO DO RUN        │
│                                                 │  (sticky, sempre visível)
│  Output dir   [ /data/out            ] [Browse] │  Samples:   12 PE      │
│                                                 │  Profile:   docker     │
│  ┌─ Reads/assemblies ─────────────────────────┐ │  Assembler: Unicycler  │
│  │ Base folder [ /data/reads       ] [Browse] │ │  Threads:   8 · 32 GB  │
│  │ Species [__________]  Genome size [▼]       │ │                        │
│  │ ☑ subfolders ☑ FASTA ☐ SE→ONT …             │ │  ── Command preview ── │
│  │            [ 🔍 Scan & build FOFN ]          │ │  nextflow run          │
│  └─────────────────────────────────────────────┘ │  bactopia/bactopia …   │
│  ▸ 12 samples · PE=10, ONT=2   [Edit sheet]      │  [Copy]                │
│  ▸ QC thresholds (avançado, recolhido)          │                        │
│                                    [ Next → ]    │  [ ▶ Run ]  (habilita  │
│                                                 │   quando FOFN pronto)  │
└───────────────────────────────────────────────┴───────────────────────┘
```
Mudanças-chave: preview + botão Run migram para um rail sticky à direita (não só no último passo);
QC thresholds e issues ficam recolhidos por padrão; contadores de runtype viram badges no topo do editor.

### 5.2 Monitor de run com timeline de estágios (substitui o code_block cru)
```
┌── Run a1b2c3  ● live ───────────────────────  [■ Stop]  [Copy log] ──┐
│  Gather ✔ ─ QC ✔ ─ Assembler ◐ (SAMPLE7) ─ Annotation ○ ─ Typing ○  │
│  ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▯▯▯▯▯   completed=8  failed=0  cached=3          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ [12:03] ASSEMBLER:UNICYCLER (SAMPLE7)                          │  │
│  │ …                                            (tail, autoscroll) │  │
│  └───────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```
`progress.parse()` já extrai stages/current/completed/failed — basta promovê-los a uma timeline visual
em vez de deixar o texto cru como protagonista. Botão Stop com confirmação.

### 5.3 Dashboard de Runs
Cabeçalho com cartões de status ("2 running · 5 success · 1 failed"), filtro por status/página, e a
linha selecionada expande para cmd + live log — em vez do painel único atual abaixo da tabela.

---

## 6. Roadmap sugerido

**Sprint 1 — Estabilizar processos (crítico, ~2 dias)**
1. H1: `start_new_session=True` + kill por grupo (SIGINT→SIGTERM→SIGKILL).
2. H2: persistir `pid`/`pgid` no history; `reconcile_orphans()` no boot; `cancel_stale` mata de verdade.
3. H4: `run.sh` detecta instância/porta anterior e oferece parar; `stop_bear.sh`; truncar/rotacionar log.
4. `update_bear.sh`: parar o app antes de atualizar.

**Sprint 2 — Performance & robustez (~2 dias)**
5. H3: coalescer flushes do log + parser de progresso incremental.
6. M1: history em SQLite (ou file-lock).
7. M4: introduzir `logging`; parar de mascarar falhas.
8. M5: discovery em background.

**Sprint 3 — Qualidade & UX (~3 dias)**
9. M6: extrair builders p/ `core/`; `RunnableMixin`.
10. L3: migrar testes p/ pytest + GitHub Actions; cobrir `runner`.
11. UX: rail de preview persistente (§5.1), timeline de run (§5.2), confirmação de Stop, idioma único,
    passe de acessibilidade.

---

## 7. Pontos positivos (manter)
Separação core/pages/components; `WizardMixin`; disciplina de `shlex.quote`; parser de progresso/falha;
pré-check de daemon Docker; FOFN editável + presets; verificador de update; installer idempotente com
smoke test. A base é boa — o trabalho é endurecer o ciclo de vida dos processos e o streaming.
