# app_bactopia_tools.py — Bactopia UI Local (Ferramentas oficiais via --wf)
# ---------------------------------------------------------------------
# Execução:  streamlit run app_bactopia_tools.py
# Requisitos: streamlit>=1.30; Nextflow + (Docker|Apptainer)
# ---------------------------------------------------------------------

import os
import shlex
import time
import pathlib
import subprocess
import re
import shutil
import asyncio
import html
import threading
import hashlib
import gzip
from typing import List
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components

# ============================= Config =============================
st.set_page_config(page_title="Bactopia — Ferramentas", layout="wide")

def _st_rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()

APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
DEFAULT_OUTDIR = str((pathlib.Path.cwd() / "bactopia_out").resolve())

# ============================= Helps (popovers) =============================
def help_popover(label: str, text: str):
    with st.popover(label):
        st.markdown(text)

def help_header(title_md: str, help_key: str, ratio=(4,1)):
    c1, c2 = st.columns(ratio)
    with c1:
        st.markdown(title_md)
    with c2:
        help_popover("❓ Ajuda", HELP[help_key])

HELP = {}

HELP["amostras"] = """
**Seleção de amostras**
- A lista acima é inferida das pastas dentro de `--bactopia` (uma pasta por amostra).
- O app gera automaticamente um arquivo `--include` com as amostras selecionadas.

**--include / --exclude (nos campos do Pangenome)**
- Passe **caminho de um arquivo TXT**, com **um nome de amostra por linha** (ex.: `sampleA`).
- Esses nomes devem **coincidir exatamente** com as pastas das amostras em `--bactopia`.
- `--include` (no bloco do Pangenome) **sobrescreve** o include automático da UI.
- `--exclude` remove amostras do conjunto atual.
- Evite vírgulas/cabeçalhos; linhas vazias são ignoradas. Prefira caminhos **absolutos**.
"""

HELP["gerais"] = """
**Parâmetros gerais do Nextflow/Bactopia**
- **`-profile`**: ambiente de execução. Use `docker` (containers Docker), `singularity` (Apptainer) ou `standard` (nativo).
- **`--max_cpus`**: limite global de *threads* para o agendador do Nextflow (não é por-tarefa).
- **`--max_memory`**: teto global de memória (ex.: `64.GB`). Tarefas acima disso serão enfileiradas.
- **`-resume`**: reaproveita etapas já concluídas (cache do Nextflow). Recomendado deixar **ligado**.
- **`Extras`**: flags cruas **adicionais** (ex.: `-with-report report.html` ou params extras do Bactopia).
"""

HELP["pangenome"] = """
**Workflow Pangenome — visão geral**
- Entrada: amostras do `--bactopia` (GFF3 das anotações). Opcionalmente inclua **referências** de RefSeq com `--species` ou `--accessions`.
- **Engine**: *Panaroo* (padrão), *PIRATE* ou *Roary*.
  - **Panaroo** (graph-based; corrige anotações; robusto para genomas fragmentados).
  - **PIRATE** (múltiplos limiares de identidade; panorama rico de presença/ausência).
  - **Roary** (rápido e direto; ajustes simples de identidade/core).
- Árvore: **IQ-TREE** sobre o alinhamento **core** (+ opção de mascarar recombinação).
- Extras: **snp-dists** (matriz de distâncias), **Scoary** (associação gene-fenótipo).

**Boas práticas**
- Use `--species` *ou* `--accessions` para ancorar em referências canônicas.
- Ative `--skip_recombination` **somente** se recombinação for irrelevante ao conjunto.
- Para suporte robusto: use **um** ou **ambos** (**`--bb`**/*bootstrap* e **`--alrt`**), ciente do maior tempo.
"""

HELP["iqtree"] = """
**IQ-TREE (filogenia)**
- **`--iqtree_model`**: modelo (ex.: `GTR+G`). Em branco → IQ-TREE escolhe (*ModelFinder*).
- **`--bb`**: *ultrafast bootstrap* (ex.: `1000`). Maior = suporte mais estável, mais tempo.
- **`--alrt`**: *approximate LRT* (ex.: `1000`). Alternativo/complementar ao bootstrap.
- **`--asr`**: reconstrução ancestral (pode ser demorado).
- **`--iqtree_opts`**: opções **diretas** ao IQ-TREE (ex.: `-nt AUTO --safe`).
"""

HELP["panaroo"] = """
**Panaroo (engine)**
- **`--panaroo_mode`**: estratégia (`strict`, `sensitive`, ...).
- **`--panaroo_alignment`**: quais genes alinhar (ex.: `core`, `all`).
- **`--panaroo_aligner`**: alinhador (ex.: `mafft`).
- **`--panaroo_core_threshold`**: fração mínima para gene **core** (ex.: `0.95`).
- **`--panaroo_threshold`**: identidade mínima para **ortólogos**.
- **`--panaroo_family_threshold`**: identidade mínima para famílias.
- **`--len_dif_percent`**: tolerância de diferença de **comprimento**.
- **`--merge_paralogs`**: tenta unir parálogos.
- **`--panaroo_opts`**: passa opções cruas ao Panaroo.
"""

HELP["pirate"] = """
**PIRATE (engine)**
- **`--steps`**: identidades para *clustering* (ex.: `50,60,70,80,90,95,98`).
- **`--features`**: tipos (ex.: `CDS`).
- **`--para_off`**: não separar parálogos.
- **`--z`**: reter intermediários.
- **`--pan_opt`**: opções cruas ao PIRATE.
"""

HELP["roary"] = """
**Roary (engine)**
- **`--i`**: identidade mínima BLASTp (ex.: `95`).
- **`--cd`**: % para definir **core** (ex.: `99`).
- **`--g`**: limite de famílias de genes (ex.: `50000`).
- **`--iv`**: *MCL inflation* (granularidade).
- **`--s`**: não separar parálogos.
- **`--ap`**: permitir parálogos no **core**.
- **`--use_prank`**: usa PRANK para alinhamentos de genes.
"""

HELP["prokka"] = """
**Prokka (re-anotação de referências)**
- **`--proteins`**: FASTA com proteínas de referência para guiar anotações.
- **`--prokka_opts`**: opções cruas do Prokka (ex.: `--kingdom Bacteria --genus Escherichia`).
"""

HELP["scoary_snpdists"] = """
**Scoary & SNP-dists**
- **`--traits`**: CSV/TSV com fenótipos (nomes de amostra **idênticos** aos do pangenome).
- **`--p_value_cutoff`** / **`--correction`** / **`--start_col`**: controles de significância/parse.
- **`--permute`**: ativa permutações (mais lento).
- **`--csv` (SNP-dists)**: exporta matriz em CSV além do TSV padrão.
"""

HELP["amrfinderplus"] = """
**AMRFinderPlus**
- Detecta genes/mutações de **resistência** e **virulência**.
- **`--plus`** inclui alvos adicionais.
- **`--mutation_all`** reporta SNPs relevantes.
- **`--ident_min` / `--coverage_min`**: mínimos de identidade/cobertura.
- **`--organism`**: restringe a busca por táxon (melhora precisão).
- Demais *switches* refinam a saída; use o campo “Extras” para opções cruas.
"""

HELP["rgi"] = """
**RGI (CARD)**
- Predição de **AMR** usando **CARD**.
- **`--use_diamond`**: acelera via DIAMOND (recomendado).
- **`--include_loose`**: inclui acertos *loose*.
- **`--exclude_nudge`**: remove *nudged hits*.
- **`--frequency`**, **`--category`**, **`--cluster`**, **`--display`**: refinam filtros/saída.
"""

HELP["mlst"] = """
**MLST**
- **`--scheme`**: esquema (ex.: `ecoli`, `staphylococcus_aureus`).
- **`--minid` / `--mincov` / `--minscore`**: mínimos de identidade, cobertura e escore.
- **`--nopath`**: não resolve *pathways* (alguns esquemas).
"""

HELP["mashtree"] = """
**Mashtree**
- Árvore rápida via *sketches* do Mash.
- **`--kmerlength`** / **`--sketchsize`**: controlam resolução/tempo.
- **`--trunclength`**, **`--genomesize`**, **`--mindepth`**, **`--sortorder`**: ajustes finos da construção.
- **`--save_sketches`**: salva *sketches* para reuso.
"""

HELP["plasmidfinder"] = """
**PlasmidFinder**
- Identifica plasmídeos em isolados bacterianos (genoma total ou parcial).
- **`--pf_mincov`**: cobertura mínima (proporção; ex.: `0.6` = 60%) para considerar um *hit*.
- **`--pf_threshold`**: identidade mínima (proporção; ex.: `0.9` = 90%) para considerar um *hit*.
- Demais parâmetros seguem o padrão Bactopia Tools (`--outdir`, `--datasets`, etc.). Use “Extras PlasmidFinder” se precisar passar opções adicionais.
"""

# ============================= Utils =============================
def ensure_state_dir():
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)

def which(cmd: str):
    from shutil import which as _which
    return _which(cmd)

def nextflow_available():
    return which("nextflow") is not None

def have_tool(name: str) -> bool:
    return which(name) is not None

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def _strip_ansi(s: str) -> str:
    return ANSI_ESCAPE.sub("", s)

def _normalize_linebreaks(chunk: str) -> list[str]:
    if not chunk:
        return []
    chunk = _strip_ansi(chunk).replace("\r", "\n")
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    return [p.rstrip() for p in chunk.split("\n") if p.strip() != ""]

async def _async_read_stream(stream, log_q: Queue, stop_event: threading.Event):
    while True:
        line = await stream.readline()
        if not line:
            break
        s = line.decode(errors="replace")
        for sub in _normalize_linebreaks(s):
            log_q.put(sub)
        if stop_event.is_set():
            break

async def _async_exec(full_cmd: str, log_q: Queue, status_q: Queue, stop_event: threading.Event):
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash", "-lc", full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        status_q.put(("error", f"Falha ao iniciar processo: {e}"))
        return
    t_out = asyncio.create_task(_async_read_stream(proc.stdout, log_q, stop_event))
    t_err = asyncio.create_task(_async_read_stream(proc.stderr, log_q, stop_event))
    while True:
        if stop_event.is_set():
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()
            except ProcessLookupError:
                pass
            break
        if proc.returncode is not None:
            break
        await asyncio.sleep(0.1)
    try:
        await asyncio.gather(t_out, t_err)
    except Exception:
        pass
    rc = await proc.wait()
    status_q.put(("rc", rc))

def _thread_entry(full_cmd: str, log_q: Queue, status_q: Queue, stop_event: threading.Event):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_exec(full_cmd, log_q, status_q, stop_event))
    finally:
        loop.close()

def start_async_runner_ns(full_cmd: str, ns: str):
    log_q = Queue()
    status_q = Queue()
    stop_event = threading.Event()
    th = threading.Thread(
        target=_thread_entry,
        args=(full_cmd, log_q, status_q, stop_event),
        daemon=True,
    )
    th.start()
    st.session_state[f"{ns}_running"] = True
    st.session_state[f"{ns}_log_q"] = log_q
    st.session_state[f"{ns}_status_q"] = status_q
    st.session_state[f"{ns}_stop_event"] = stop_event
    st.session_state[f"{ns}_thread"] = th
    st.session_state[f"{ns}_live_log"] = []

def request_stop_ns(ns: str):
    ev = st.session_state.get(f"{ns}_stop_event")
    if ev and not ev.is_set():
        ev.set()

def drain_log_queue_ns(ns: str, tail_limit: int = 200, max_pull: int = 500):
    q: Queue = st.session_state.get(f"{ns}_log_q")
    if not q:
        return
    buf = st.session_state.get(f"{ns}_live_log", [])
    pulled = 0
    while pulled < max_pull:
        try:
            line = q.get_nowait()
        except Empty:
            break
        buf.append(line)
        pulled += 1
    if len(buf) > tail_limit:
        buf[:] = buf[-tail_limit:]
    st.session_state[f"{ns}_live_log"] = buf

def render_log_box_ns(ns: str, height: int = 520):
    lines = st.session_state.get(f"{ns}_live_log", [])
    content = html.escape("\n".join(lines)) if lines else ""
    components.html(
        f"""
    <div id=\"logbox_{ns}\" style=
        "
        width:100%; height:{height-40}px; margin:0 auto; padding:12px;
        overflow-y:auto; overflow-x:auto; background:#0b0b0b; color:#e6e6e6;
        border-radius:10px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
        font-size:13px; line-height:1.35;">
      <pre style="margin:0; white-space: pre;">{content or "&nbsp;"}</pre>
    </div>
    <script>const el=document.getElementById("logbox_{ns}"); if(el){{el.scrollTop=el.scrollHeight;}}</script>
    """,
        height=height,
        scrolling=False,
    )

def check_status_and_finalize_ns(ns: str, status_box):
    sq: Queue = st.session_state.get(f"{ns}_status_q")
    if not sq:
        return False
    finalized = False
    msg = None
    rc = None
    try:
        while True:
            kind, payload = sq.get_nowait()
            if kind == "error":
                msg = payload
                finalized = True
                rc = -1
            elif kind == "rc":
                rc = int(payload)
                finalized = True
    except Empty:
        pass
    if finalized:
        st.session_state[f"{ns}_running"] = False
        st.session_state[f"{ns}_thread"] = None
        st.session_state[f"{ns}_stop_event"] = None
        if rc == 0:
            status_box.success("Concluído com sucesso.")
        else:
            status_box.error(msg or f"Execução terminou com código {rc}. Veja o log abaixo.")
    return finalized

# ============================= Página =============================
st.title("🧰 Bactopia — Ferramentas oficiais")

# Seleção de pasta/amostras
st.subheader("Seleção de pasta e amostras")
help_popover("❓ Ajuda", HELP["amostras"])

def discover_samples_from_outdir(outdir: str) -> List[str]:
    p = pathlib.Path(outdir)
    if not p.exists() or not p.is_dir():
        return []
    samples = []
    for child in sorted(p.iterdir(), key=lambda x: x.name):
        if not child.is_dir():
            continue
        if child.name.startswith("bactopia-") or child.name in {"bactopia-runs"}:
            continue
        if (child / "main").exists() or (child / "tools").exists():
            samples.append(child.name)
    return samples

# input roots
bt_outdir = st.text_input(
    "Pasta de resultados do Bactopia",
    value=st.session_state.get("bt_outdir", st.session_state.get("outdir", DEFAULT_OUTDIR)),
    key="bt_outdir",
)
samples = discover_samples_from_outdir(bt_outdir) if bt_outdir else []
if samples:
    sel = st.multiselect(
        "Amostras",
        options=samples,
        default=st.session_state.get("bt_selected_samples", samples),
        key="bt_selected_samples",
    )
else:
    sel = []
    if bt_outdir:
        st.warning("Nenhuma amostra encontrada nessa pasta.")

st.divider()
st.subheader("Ferramentas (oficiais)")
r1 = st.columns(5)
with r1[0]:
    st.checkbox("amrfinderplus", value=st.session_state.get("bt_run_amrfinderplus", False), key="bt_run_amrfinderplus")
with r1[1]:
    st.checkbox("rgi", value=st.session_state.get("bt_run_rgi", False), key="bt_run_rgi")
with r1[2]:
    st.checkbox("abricate", value=st.session_state.get("bt_run_abricate", False), key="bt_run_abricate")
with r1[3]:
    st.checkbox("mobsuite", value=st.session_state.get("bt_run_mobsuite", False), key="bt_run_mobsuite")
with r1[4]:
    st.checkbox("mlst", value=st.session_state.get("bt_run_mlst", False), key="bt_run_mlst")

r2 = st.columns(5)
with r2[0]:
    st.checkbox("pangenome", value=st.session_state.get("bt_run_pangenome", False), key="bt_run_pangenome")
with r2[1]:
    st.checkbox("mashtree", value=st.session_state.get("bt_run_mashtree", False), key="bt_run_mashtree")
with r2[2]:
    st.checkbox("plasmidfinder", value=st.session_state.get("bt_run_plasmidfinder", False), key="bt_run_plasmidfinder")

with st.expander("Parâmetros gerais", expanded=True):
    bt_profile = st.selectbox("Perfil (-profile)", ["docker", "singularity", "standard"], index=0, key="bt_profile")
    bt_threads = st.slider("--max_cpus", 0, min(os.cpu_count() or 64, 128), 0, 1, key="bt_threads")
    bt_memory_gb = st.slider("--max_memory (GB)", 0, 256, 0, 1, key="bt_memory_gb")
    bt_resume = st.checkbox("-resume", value=True, key="bt_resume")
    bt_extra = st.text_input("Extras (linha crua, opcional)", key="bt_extra", value=st.session_state.get("bt_extra", ""))
    help_popover("❓ Ajuda (parâmetros gerais)", HELP["gerais"])

# Opções específicas
if st.session_state.get("bt_run_abricate"):
    st.markdown("**ABRicate — opções**")
    st.text_input(
        "--abricate_db (ex.: ncbi,plasmidfinder)",
        key="bt_abricate_db",
        value=st.session_state.get("bt_abricate_db", ""),
    )

# --- AMRFinderPlus ---
if st.session_state.get("bt_run_amrfinderplus"):
    help_header("**AMRFinderPlus — opções**", "amrfinderplus")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox("--plus", value=st.session_state.get("bt_amrfinderplus_plus", True), key="bt_amrfinderplus_plus")
        st.checkbox(
            "--mutation_all",
            value=st.session_state.get("bt_amrfinderplus_mutation_all", False),
            key="bt_amrfinderplus_mutation_all",
        )
    with c2:
        st.number_input(
            "--ident_min",
            0.0,
            100.0,
            value=st.session_state.get("bt_amrfinderplus_ident_min", 90.0),
            step=0.5,
            key="bt_amrfinderplus_ident_min",
        )
        st.number_input(
            "--coverage_min",
            0.0,
            100.0,
            value=st.session_state.get("bt_amrfinderplus_coverage_min", 50.0),
            step=0.5,
            key="bt_amrfinderplus_coverage_min",
        )
    with c3:
        st.text_input(
            "--organism (ex.: Enterobacteriaceae)",
            value=st.session_state.get("bt_amrfinderplus_organism", ""),
            key="bt_amrfinderplus_organism",
        )
    c4, c5, c6 = st.columns(3)
    with c4:
        st.checkbox(
            "--report_common",
            value=st.session_state.get("bt_amrfinderplus_report_common", False),
            key="bt_amrfinderplus_report_common",
        )
    with c5:
        st.checkbox(
            "--report_all_equal_best",
            value=st.session_state.get("bt_amrfinderplus_report_all_equal_best", False),
            key="bt_amrfinderplus_report_all_equal_best",
        )
    with c6:
        st.checkbox(
            "--allow_overlap",
            value=st.session_state.get("bt_amrfinderplus_allow_overlap", False),
            key="bt_amrfinderplus_allow_overlap",
        )
    st.checkbox(
        "--exclude_quick_need_prediction",
        value=st.session_state.get("bt_amrfinderplus_exclude_quick_need_prediction", False),
        key="bt_amrfinderplus_exclude_quick_need_prediction",
    )
    st.text_input(
        "Extras AMRFinderPlus (linha crua/append)",
        value=st.session_state.get("bt_amrfinderplus_extra", ""),
        key="bt_amrfinderplus_extra",
    )

# --- RGI ---
if st.session_state.get("bt_run_rgi"):
    help_header("**RGI (CARD) — opções**", "rgi")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.checkbox("--use_diamond", value=st.session_state.get("bt_rgi_use_diamond", True), key="bt_rgi_use_diamond")
    with c2:
        st.checkbox(
            "--include_loose",
            value=st.session_state.get("bt_rgi_include_loose", False),
            key="bt_rgi_include_loose",
        )
    with c3:
        st.checkbox(
            "--exclude_nudge",
            value=st.session_state.get("bt_rgi_exclude_nudge", False),
            key="bt_rgi_exclude_nudge",
        )
    with c4:
        st.text_input(
            "--frequency (ex.: 'perfect,strict')",
            value=st.session_state.get("bt_rgi_frequency", ""),
            key="bt_rgi_frequency",
        )
    c5, c6, c7 = st.columns(3)
    with c5:
        st.text_input("--category", value=st.session_state.get("bt_rgi_category", ""), key="bt_rgi_category")
    with c6:
        st.text_input("--cluster", value=st.session_state.get("bt_rgi_cluster", ""), key="bt_rgi_cluster")
    with c7:
        st.text_input("--display", value=st.session_state.get("bt_rgi_display", ""), key="bt_rgi_display")
    st.text_input(
        "Extras RGI (linha crua/append)",
        value=st.session_state.get("bt_rgi_extra", ""),
        key="bt_rgi_extra",
    )

# --- MLST ---
if st.session_state.get("bt_run_mlst"):
    help_header("**MLST — opções**", "mlst")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.text_input("--scheme", value=st.session_state.get("bt_mlst_scheme", ""), key="bt_mlst_scheme")
    with c2:
        st.number_input(
            "--minid",
            0.0,
            100.0,
            value=st.session_state.get("bt_mlst_minid", 95.0),
            step=0.5,
            key="bt_mlst_minid",
        )
    with c3:
        st.number_input(
            "--mincov",
            0.0,
            100.0,
            value=st.session_state.get("bt_mlst_mincov", 50.0),
            step=0.5,
            key="bt_mlst_mincov",
        )
    with c4:
        st.number_input(
            "--minscore",
            0.0,
            100.0,
            value=st.session_state.get("bt_mlst_minscore", 0.0),
            step=0.5,
            key="bt_mlst_minscore",
        )
    with c5:
        st.checkbox("--nopath", value=st.session_state.get("bt_mlst_nopath", False), key="bt_mlst_nopath")

# --- PlasmidFinder ---
if st.session_state.get("bt_run_plasmidfinder"):
    help_header("**PlasmidFinder — opções**", "plasmidfinder")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "--pf_mincov (0–1, ex.: 0.6)",
            0.0,
            1.0,
            value=st.session_state.get("bt_pf_mincov", 0.6),
            step=0.05,
            key="bt_pf_mincov",
        )
    with c2:
        st.number_input(
            "--pf_threshold (0–1, ex.: 0.9)",
            0.0,
            1.0,
            value=st.session_state.get("bt_pf_threshold", 0.9),
            step=0.05,
            key="bt_pf_threshold",
        )
    st.text_input(
        "Extras PlasmidFinder (linha crua/append)",
        value=st.session_state.get("bt_plasmidfinder_extra", ""),
        key="bt_plasmidfinder_extra",
    )

# --- Pangenome subset (ATUALIZADO) ---
if st.session_state.get("bt_run_pangenome"):
    help_header("**Pangenome — opções principais**", "pangenome")
    st.caption(
        "Inclui engine (Panaroo/PIRATE/Roary) + IQ-TREE + Prokka + Scoary + SNP-dists. "
        "Use 'Extras' gerais para flags adicionais do Nextflow."
    )

    # Engine
    c1, c2 = st.columns([1, 3])
    with c1:
        st.radio(
            "Engine",
            options=["Panaroo", "PIRATE", "Roary"],
            index=["Panaroo", "PIRATE", "Roary"].index(
                st.session_state.get("bt_pangenome_engine", "Panaroo")
            ),
            key="bt_pangenome_engine",
        )
    with c2:
        help_popover("ℹ️ Engine (Panaroo/PIRATE/Roary)", HELP["pangenome"])

    # Seleção adicional de amostras (opcional; aplica só ao pangenome)
    st.markdown("_Seleção extra de amostras (opcional)_")
    cc1, cc2 = st.columns(2)
    with cc1:
        st.text_input(
            "Arquivo --include (um nome por linha) [⚠️ sobrescreve o include automático]",
            value=st.session_state.get("bt_pangenome_include", ""),
            key="bt_pangenome_include",
        )
    with cc2:
        st.text_input(
            "Arquivo --exclude (um nome por linha)",
            value=st.session_state.get("bt_pangenome_exclude", ""),
            key="bt_pangenome_exclude",
        )

    # Referências baixadas (RefSeq)
    st.markdown("_Genomas de referência (RefSeq; opcional)_")
    c3, c4 = st.columns(2)
    with c3:
        st.text_input(
            "--species (ex.: Escherichia coli)",
            value=st.session_state.get("bt_pangenome_species", ""),
            key="bt_pangenome_species",
        )
    with c4:
        st.text_input(
            "--accessions (arquivo com 1 acesso por linha OU CSV)",
            value=st.session_state.get("bt_pangenome_accessions", ""),
            key="bt_pangenome_accessions",
        )

    # Recombinação
    st.checkbox(
        "--skip_recombination (pular ClonalFrameML)",
        value=st.session_state.get("bt_pangenome_skip_recombination", False),
        key="bt_pangenome_skip_recombination",
    )

    # IQ-TREE
    help_header("_IQ-TREE_", "iqtree", ratio=(3, 1))
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        st.text_input(
            "--iqtree_model",
            value=st.session_state.get("bt_iqtree_model", ""),
            key="bt_iqtree_model",
        )
    with q2:
        st.number_input(
            "--bb",
            0,
            5000,
            value=st.session_state.get("bt_iqtree_bb", 0),
            step=100,
            key="bt_iqtree_bb",
        )
    with q3:
        st.number_input(
            "--alrt",
            0,
            5000,
            value=st.session_state.get("bt_iqtree_alrt", 0),
            step=100,
            key="bt_iqtree_alrt",
        )
    with q4:
        st.checkbox("--asr", value=st.session_state.get("bt_iqtree_asr", False), key="bt_iqtree_asr")
    st.text_input(
        "iqtree_opts (append)",
        value=st.session_state.get("bt_iqtree_opts", ""),
        key="bt_iqtree_opts",
    )

    # Panaroo (visível se engine == Panaroo)
    if st.session_state.get("bt_pangenome_engine", "Panaroo") == "Panaroo":
        help_header("_Panaroo_", "panaroo", ratio=(3, 1))
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            st.text_input(
                "--panaroo_mode",
                value=st.session_state.get("bt_panaroo_mode", ""),
                key="bt_panaroo_mode",
            )
        with p2:
            st.text_input(
                "--panaroo_alignment",
                value=st.session_state.get("bt_panaroo_alignment", ""),
                key="bt_panaroo_alignment",
            )
        with p3:
            st.text_input(
                "--panaroo_aligner",
                value=st.session_state.get("bt_panaroo_aligner", ""),
                key="bt_panaroo_aligner",
            )
        with p4:
            st.checkbox(
                "--merge_paralogs",
                value=st.session_state.get("bt_panaroo_merge_paralogs", False),
                key="bt_panaroo_merge_paralogs",
            )
        p5, p6, p7, p8 = st.columns(4)
        with p5:
            st.text_input(
                "--panaroo_core_threshold",
                value=st.session_state.get("bt_panaroo_core_threshold", ""),
                key="bt_panaroo_core_threshold",
            )
        with p6:
            st.text_input(
                "--panaroo_threshold",
                value=st.session_state.get("bt_panaroo_threshold", ""),
                key="bt_panaroo_threshold",
            )
        with p7:
            st.text_input(
                "--panaroo_family_threshold",
                value=st.session_state.get("bt_panaroo_family_threshold", ""),
                key="bt_panaroo_family_threshold",
            )
        with p8:
            st.text_input(
                "--len_dif_percent",
                value=st.session_state.get("bt_panaroo_len_dif_percent", ""),
                key="bt_panaroo_len_dif_percent",
            )
        st.text_input(
            "panaroo_opts (append)",
            value=st.session_state.get("bt_panaroo_opts", ""),
            key="bt_panaroo_opts",
        )

    # PIRATE (visível se engine == PIRATE)
    if st.session_state.get("bt_pangenome_engine", "Panaroo") == "PIRATE":
        help_header("_PIRATE_", "pirate", ratio=(3, 1))
        r1c, r2c, r3c, r4c = st.columns(4)
        with r1c:
            st.text_input(
                "--steps (ex.: 50,60,70,80,90,95,98)",
                value=st.session_state.get("bt_pirate_steps", ""),
                key="bt_pirate_steps",
            )
        with r2c:
            st.text_input(
                "--features (ex.: CDS)",
                value=st.session_state.get("bt_pirate_features", ""),
                key="bt_pirate_features",
            )
        with r3c:
            st.checkbox(
                "--para_off (desativa identificação de parálogos)",
                value=st.session_state.get("bt_pirate_para_off", False),
                key="bt_pirate_para_off",
            )
        with r4c:
            st.checkbox(
                "--z (reter intermediários)",
                value=st.session_state.get("bt_pirate_z", False),
                key="bt_pirate_z",
            )
        st.text_input(
            "pan_opt (append p/ engine)",
            value=st.session_state.get("bt_pirate_opts", ""),
            key="bt_pirate_opts",
        )

    # Roary (visível se engine == Roary)
    if st.session_state.get("bt_pangenome_engine", "Panaroo") == "Roary":
        help_header("_Roary_", "roary", ratio=(3, 1))
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            st.checkbox(
                "--use_prank",
                value=st.session_state.get("bt_roary_use_prank", False),
                key="bt_roary_use_prank",
            )
        with t2:
            st.text_input(
                "--i (identidade %, ex.: 95)",
                value=st.session_state.get("bt_roary_i", ""),
                key="bt_roary_i",
            )
        with t3:
            st.text_input(
                "--cd (% core definition, ex.: 99)",
                value=st.session_state.get("bt_roary_cd", ""),
                key="bt_roary_cd",
            )
        with t4:
            st.text_input(
                "--g (máx. clusters, ex.: 50000)",
                value=st.session_state.get("bt_roary_g", ""),
                key="bt_roary_g",
            )
        u1, u2 = st.columns(2)
        with u1:
            st.checkbox(
                "--s (não separar parálogos)",
                value=st.session_state.get("bt_roary_s", False),
                key="bt_roary_s",
            )
        with u2:
            st.checkbox(
                "--ap (parálogos no core)",
                value=st.session_state.get("bt_roary_ap", False),
                key="bt_roary_ap",
            )
        st.text_input(
            "--iv (MCL inflation, ex.: 1.5)",
            value=st.session_state.get("bt_roary_iv", ""),
            key="bt_roary_iv",
        )

    # Prokka
    help_header("_Prokka (opcional)_", "prokka", ratio=(3, 1))
    st.text_input(
        "--proteins (FASTA; opcional)",
        value=st.session_state.get("bt_prokka_proteins", ""),
        key="bt_prokka_proteins",
    )
    st.text_input(
        "prokka_opts (append)",
        value=st.session_state.get("bt_prokka_opts", ""),
        key="bt_prokka_opts",
    )

    # Scoary & SNP-dists
    help_header("_Scoary & SNP-dists_", "scoary_snpdists", ratio=(3, 1))
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.text_input(
            "--traits (CSV/TSV)",
            value=st.session_state.get("bt_scoary_traits", ""),
            key="bt_scoary_traits",
        )
    with s2:
        st.text_input(
            "--p_value_cutoff",
            value=st.session_state.get("bt_scoary_p_value_cutoff", ""),
            key="bt_scoary_p_value_cutoff",
        )
    with s3:
        st.text_input(
            "--correction",
            value=st.session_state.get("bt_scoary_correction", ""),
            key="bt_scoary_correction",
        )
    with s4:
        st.text_input(
            "--start_col",
            value=st.session_state.get("bt_scoary_start_col", ""),
            key="bt_scoary_start_col",
        )
    st.checkbox("SNP-dists: --csv", value=st.session_state.get("bt_snpdists_csv", False), key="bt_snpdists_csv")

# --- Mashtree ---
if st.session_state.get("bt_run_mashtree"):
    help_header("**Mashtree — opções**", "mashtree")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.number_input(
            "--trunclength",
            0,
            1000000,
            value=st.session_state.get("bt_mashtree_trunclength", 0),
            step=100,
            key="bt_mashtree_trunclength",
        )
    with c2:
        st.text_input(
            "--sortorder (ex.: avg)",
            value=st.session_state.get("bt_mashtree_sortorder", ""),
            key="bt_mashtree_sortorder",
        )
    with c3:
        st.number_input(
            "--genomesize",
            0,
            100000000,
            value=st.session_state.get("bt_mashtree_genomesize", 0),
            step=100000,
            key="bt_mashtree_genomesize",
        )
    with c4:
        st.number_input(
            "--mindepth",
            0,
            100,
            value=st.session_state.get("bt_mashtree_mindepth", 0),
            step=1,
            key="bt_mashtree_mindepth",
        )
    c5, c6 = st.columns(2)
    with c5:
        st.number_input(
            "--kmerlength",
            1,
            64,
            value=st.session_state.get("bt_mashtree_kmerlength", 21),
            step=1,
            key="bt_mashtree_kmerlength",
        )
    with c6:
        st.number_input(
            "--sketchsize",
            1,
            200000,
            value=st.session_state.get("bt_mashtree_sketchsize", 10000),
            step=100,
            key="bt_mashtree_sketchsize",
        )
    st.checkbox(
        "--save_sketches",
        value=st.session_state.get("bt_mashtree_save_sketches", False),
        key="bt_mashtree_save_sketches",
    )

# monta arquivo --include
def write_include_file(outdir: str, samples: List[str]) -> str:
    ensure_state_dir()
    fname = APP_STATE_DIR / f"include_{hashlib.md5((outdir + '|' + ';'.join(samples)).encode()).hexdigest()[:10]}.txt"
    with open(fname, "w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(s + "\n")
    return str(fname)

def bt_nextflow_cmd(
    tool: str,
    outdir: str,
    include_file: str,
    profile: str,
    threads: int | None = None,
    memory_gb: int | None = None,
    resume: bool = True,
    extra: List[str] | None = None,
) -> str:
    base = [
        "nextflow",
        "run",
        "bactopia/bactopia",
        "-profile",
        profile,
        "--wf",
        tool,
        "--bactopia",
        outdir,
        "--include",
        include_file,
    ]
    if threads and threads > 0:
        base += ["--max_cpus", str(threads)]
    if memory_gb and memory_gb > 0:
        base += ["--max_memory", f"{memory_gb}.GB"]
    if resume:
        base += ["-resume"]
    if extra:
        base += extra
    if (st.session_state.get("bt_extra") or "").strip():
        base += shlex.split(st.session_state["bt_extra"])
    return " ".join(shlex.quote(x) for x in base)

# ======================= MobSuite plasmids extraction =======================
def extract_mobsuite_plasmids(
    bt_outdir: str,
    samples: List[str],
    dest_root: str | None = None,
    decompress_gz: bool = False,
) -> tuple[int, int, list[str]]:
    """
    Varre as amostras em bt_outdir, procura FASTA de plasmídeos do MobSuite e
    copia (e opcionalmente descompacta) para dest_root/<sample>/.

    Retorna:
        (n_samples_ok, n_files_total, logs)
    """
    logs: list[str] = []
    if not bt_outdir:
        logs.append("bt_outdir vazio.")
        return 0, 0, logs

    root = pathlib.Path(bt_outdir)
    if not root.exists():
        logs.append(f"Diretório não existe: {root}")
        return 0, 0, logs

    if dest_root is None:
        dest_root = str(root / "plasmids_mobsuite")

    dest_root_path = pathlib.Path(dest_root)
    dest_root_path.mkdir(parents=True, exist_ok=True)

    samples_ok = 0
    files_total = 0

    for sample in samples:
        sample_dir = root / sample / "tools" / "mobsuite"
        if not sample_dir.exists():
            logs.append(f"[{sample}] pasta MobSuite não encontrada: {sample_dir}")
            continue

        # procura plasmid_*.fasta e plasmid_*.fasta.gz
        fasta_files = list(sample_dir.glob("plasmid_*.fasta")) + list(sample_dir.glob("plasmid_*.fasta.gz"))
        if not fasta_files:
            logs.append(f"[{sample}] nenhum FASTA de plasmídeo encontrado em {sample_dir}")
            continue

        out_sample_dir = dest_root_path / sample
        out_sample_dir.mkdir(parents=True, exist_ok=True)

        for src in fasta_files:
            if decompress_gz and src.suffix == ".gz":
                # descompactar para .fasta (mesmo nome sem .gz)
                dest_fa = out_sample_dir / src.stem  # remove .gz
                try:
                    with gzip.open(src, "rt") as fin, open(dest_fa, "w", encoding="utf-8") as fout:
                        fout.write(fin.read())
                    logs.append(f"[{sample}] descompactado: {src.name} -> {dest_fa}")
                    files_total += 1
                except Exception as e:
                    logs.append(f"[{sample}] ERRO ao descompactar {src}: {e}")
            else:
                # só copia o arquivo como está
                dest_file = out_sample_dir / src.name
                try:
                    shutil.copy2(src, dest_file)
                    logs.append(f"[{sample}] copiado: {src.name} -> {dest_file}")
                    files_total += 1
                except Exception as e:
                    logs.append(f"[{sample}] ERRO ao copiar {src}: {e}")

        samples_ok += 1

    if samples_ok == 0:
        logs.append("Nenhuma amostra com FASTA de plasmídeo válida foi processada.")

    return samples_ok, files_total, logs

# Barra de ações (async para Tools)
st.divider()
col1, col2 = st.columns([1, 1])
with col1:
    start_tools = st.button(
        "▶️ Executar Ferramentas (async)",
        key="btn_tools_start",
        disabled=st.session_state.get("tools_running", False),
    )
with col2:
    stop_tools = st.button(
        "⏹️ Interromper",
        key="btn_tools_stop",
        disabled=not st.session_state.get("tools_running", False),
    )

status_box_tools = st.empty()
log_zone_tools = st.empty()

if stop_tools:
    request_stop_ns("tools")
    status_box_tools.warning("Solicitada interrupção…")

if start_tools:
    if not nextflow_available():
        st.error("Nextflow não encontrado no PATH.")
    else:
        if not bt_outdir:
            st.error("Defina a 'Pasta de resultados do Bactopia'.")
        else:
            if not sel and samples:
                sel = samples
                st.session_state["bt_selected_samples"] = sel
            if not sel:
                st.error("Selecione pelo menos uma amostra.")
            else:
                include_file = write_include_file(bt_outdir, sel)
                tools_to_run = []

                # AMRFinderPlus
                if st.session_state.get("bt_run_amrfinderplus"):
                    extra = []
                    if st.session_state.get("bt_amrfinderplus_plus"):
                        extra.append("--amrfinderplus_plus")
                    if st.session_state.get("bt_amrfinderplus_mutation_all"):
                        extra.append("--amrfinderplus_mutation_all")
                    v = st.session_state.get("bt_amrfinderplus_ident_min")
                    if v not in (None, ""):
                        extra += ["--amrfinderplus_ident_min", str(v)]
                    v = st.session_state.get("bt_amrfinderplus_coverage_min")
                    if v not in (None, ""):
                        extra += ["--amrfinderplus_coverage_min", str(v)]
                    v = (st.session_state.get("bt_amrfinderplus_organism", "")).strip()
                    if v:
                        extra += ["--amrfinderplus_organism", v]
                    if st.session_state.get("bt_amrfinderplus_report_common"):
                        extra.append("--amrfinderplus_report_common")
                    if st.session_state.get("bt_amrfinderplus_report_all_equal_best"):
                        extra.append("--amrfinderplus_report_all_equal_best")
                    if st.session_state.get("bt_amrfinderplus_allow_overlap"):
                        extra.append("--amrfinderplus_allow_overlap")
                    if st.session_state.get("bt_amrfinderplus_exclude_quick_need_prediction"):
                        extra.append("--amrfinderplus_exclude_quick_need_prediction")
                    v = (st.session_state.get("bt_amrfinderplus_extra", "")).strip()
                    if v:
                        extra += shlex.split(v)
                    tools_to_run.append(("amrfinderplus", extra))

                # RGI
                if st.session_state.get("bt_run_rgi"):
                    extra = []
                    if st.session_state.get("bt_rgi_use_diamond"):
                        extra.append("--rgi_use_diamond")
                    if st.session_state.get("bt_rgi_include_loose"):
                        extra.append("--rgi_include_loose")
                    if st.session_state.get("bt_rgi_exclude_nudge"):
                        extra.append("--rgi_exclude_nudge")
                    for k, flag in [
                        ("bt_rgi_frequency", "--rgi_frequency"),
                        ("bt_rgi_category", "--rgi_category"),
                        ("bt_rgi_cluster", "--rgi_cluster"),
                        ("bt_rgi_display", "--rgi_display"),
                    ]:
                        v = (st.session_state.get(k) or "").strip()
                        if v:
                            extra += [flag, v]
                    v = (st.session_state.get("bt_rgi_extra", "")).strip()
                    if v:
                        extra += shlex.split(v)
                    tools_to_run.append(("rgi", extra))

                # ABRicate
                if st.session_state.get("bt_run_abricate"):
                    extra = []
                    if (st.session_state.get("bt_abricate_db") or "").strip():
                        extra += ["--abricate_db", st.session_state["bt_abricate_db"]]
                    tools_to_run.append(("abricate", extra))

                # MobSuite
                if st.session_state.get("bt_run_mobsuite"):
                    tools_to_run.append(("mobsuite", []))

                # MLST
                if st.session_state.get("bt_run_mlst"):
                    extra = []
                    v = (st.session_state.get("bt_mlst_scheme", "")).strip()
                    if v:
                        extra += ["--scheme", v]
                    v = st.session_state.get("bt_mlst_minid")
                    if v not in (None, ""):
                        extra += ["--minid", str(v)]
                    v = st.session_state.get("bt_mlst_mincov")
                    if v not in (None, ""):
                        extra += ["--mincov", str(v)]
                    v = st.session_state.get("bt_mlst_minscore")
                    if v not in (None, ""):
                        extra += ["--minscore", str(v)]
                    if st.session_state.get("bt_mlst_nopath"):
                        extra.append("--nopath")
                    tools_to_run.append(("mlst", extra))

                # PlasmidFinder
                if st.session_state.get("bt_run_plasmidfinder"):
                    extra = []
                    v = st.session_state.get("bt_pf_mincov")
                    if v not in (None, ""):
                        extra += ["--pf_mincov", str(v)]
                    v = st.session_state.get("bt_pf_threshold")
                    if v not in (None, ""):
                        extra += ["--pf_threshold", str(v)]
                    v = (st.session_state.get("bt_plasmidfinder_extra", "")).strip()
                    if v:
                        extra += shlex.split(v)
                    tools_to_run.append(("plasmidfinder", extra))

                # Pangenome
                if st.session_state.get("bt_run_pangenome"):
                    extra = []

                    # Engine (Panaroo é o default nas versões recentes)
                    engine = st.session_state.get("bt_pangenome_engine", "Panaroo")
                    if engine == "PIRATE":
                        extra.append("--use_pirate")
                    elif engine == "Roary":
                        extra.append("--use_roary")
                    # Panaroo (default) não precisa de flag

                    # Filtros extras (⚠️ um segundo --include pode sobrescrever o include_file global)
                    inc = (st.session_state.get("bt_pangenome_include") or "").strip()
                    exc = (st.session_state.get("bt_pangenome_exclude") or "").strip()
                    if inc:
                        extra += ["--include", inc]
                    if exc:
                        extra += ["--exclude", exc]

                    # NCBI genome download
                    species = (st.session_state.get("bt_pangenome_species") or "").strip()
                    accessions = (st.session_state.get("bt_pangenome_accessions") or "").strip()
                    if species:
                        extra += ["--species", species]
                    if accessions:
                        extra += ["--accessions", accessions]

                    # ClonalFrameML
                    if st.session_state.get("bt_pangenome_skip_recombination", False):
                        extra.append("--skip_recombination")

                    # IQ-TREE
                    v = (st.session_state.get("bt_iqtree_model", "")).strip()
                    if v:
                        extra += ["--iqtree_model", v]
                    v = st.session_state.get("bt_iqtree_bb", 0)
                    if v:
                        extra += ["--bb", str(int(v))]
                    v = st.session_state.get("bt_iqtree_alrt", 0)
                    if v:
                        extra += ["--alrt", str(int(v))]
                    if st.session_state.get("bt_iqtree_asr"):
                        extra.append("--asr")
                    v = (st.session_state.get("bt_iqtree_opts", "")).strip()
                    if v:
                        extra += ["--iqtree_opts", v]

                    # Panaroo params (somente se engine == Panaroo)
                    if engine == "Panaroo":
                        for key, flag in [
                            ("bt_panaroo_mode", "--panaroo_mode"),
                            ("bt_panaroo_alignment", "--panaroo_alignment"),
                            ("bt_panaroo_aligner", "--panaroo_aligner"),
                            ("bt_panaroo_core_threshold", "--panaroo_core_threshold"),
                            ("bt_panaroo_threshold", "--panaroo_threshold"),
                            ("bt_panaroo_family_threshold", "--panaroo_family_threshold"),
                            ("bt_panaroo_len_dif_percent", "--len_dif_percent"),
                        ]:
                            vv = (st.session_state.get(key) or "").strip()
                            if vv:
                                extra += [flag, vv]
                        if st.session_state.get("bt_panaroo_merge_paralogs"):
                            extra.append("--merge_paralogs")
                        v = (st.session_state.get("bt_panaroo_opts", "")).strip()
                        if v:
                            extra += ["--panaroo_opts", v]

                    # PIRATE params
                    if engine == "PIRATE":
                        steps = (st.session_state.get("bt_pirate_steps") or "").strip()
                        features = (st.session_state.get("bt_pirate_features") or "").strip()
                        para_off = st.session_state.get("bt_pirate_para_off", False)
                        keep_z = st.session_state.get("bt_pirate_z", False)
                        pan_opt = (st.session_state.get("bt_pirate_opts") or "").strip()
                        if steps:
                            extra += ["--steps", steps]
                        if features:
                            extra += ["--features", features]
                        if para_off:
                            extra.append("--para_off")
                        if keep_z:
                            extra.append("--z")
                        if pan_opt:
                            extra += ["--pan_opt", pan_opt]

                    # Roary params
                    if engine == "Roary":
                        if st.session_state.get("bt_roary_use_prank"):
                            extra.append("--use_prank")
                        for key, flag in [
                            ("bt_roary_i", "--i"),
                            ("bt_roary_cd", "--cd"),
                            ("bt_roary_g", "--g"),
                            ("bt_roary_iv", "--iv"),
                        ]:
                            vv = (st.session_state.get(key) or "").strip()
                            if vv:
                                extra += [flag, vv]
                        if st.session_state.get("bt_roary_s"):
                            extra.append("--s")
                        if st.session_state.get("bt_roary_ap"):
                            extra.append("--ap")

                    # Prokka
                    v = (st.session_state.get("bt_prokka_proteins", "")).strip()
                    if v:
                        extra += ["--proteins", v]
                    v = (st.session_state.get("bt_prokka_opts", "")).strip()
                    if v:
                        extra += ["--prokka_opts", v]

                    # Scoary & SNP-dists
                    v = (st.session_state.get("bt_scoary_traits", "")).strip()
                    if v:
                        extra += ["--traits", v]
                    for key, flag in [
                        ("bt_scoary_p_value_cutoff", "--p_value_cutoff"),
                        ("bt_scoary_correction", "--correction"),
                        ("bt_scoary_start_col", "--start_col"),
                    ]:
                        vv = (st.session_state.get(key) or "").strip()
                        if vv:
                            extra += [flag, vv]
                    if st.session_state.get("bt_scoary_permute"):
                        extra += ["--permute"]
                    if st.session_state.get("bt_snpdists_csv"):
                        extra += ["--csv"]

                    tools_to_run.append(("pangenome", extra))

                # Mashtree
                if st.session_state.get("bt_run_mashtree"):
                    extra = []
                    for key, flag in [
                        ("bt_mashtree_trunclength", "--trunclength"),
                        ("bt_mashtree_sortorder", "--sortorder"),
                        ("bt_mashtree_genomesize", "--genomesize"),
                        ("bt_mashtree_mindepth", "--mindepth"),
                        ("bt_mashtree_kmerlength", "--kmerlength"),
                        ("bt_mashtree_sketchsize", "--sketchsize"),
                    ]:
                        vv = st.session_state.get(key)
                        if isinstance(vv, (int, float)) and vv > 0:
                            extra += [flag, str(vv)]
                        elif isinstance(vv, str) and vv.strip():
                            extra += [flag, vv.strip()]
                    if st.session_state.get("bt_mashtree_save_sketches"):
                        extra.append("--save_sketches")
                    tools_to_run.append(("mashtree", extra))

                if not tools_to_run:
                    st.warning("Selecione ao menos uma ferramenta oficial.")
                else:
                    sub_cmds = []
                    stdbuf = shutil.which("stdbuf")
                    for tool, extra in tools_to_run:
                        cmdi = bt_nextflow_cmd(
                            tool,
                            bt_outdir,
                            include_file,
                            st.session_state.get("bt_profile", "docker"),
                            st.session_state.get("bt_threads") or None,
                            st.session_state.get("bt_memory_gb") or None,
                            resume=st.session_state.get("bt_resume", True),
                            extra=extra,
                        )
                        if stdbuf:
                            cmdi = f"{stdbuf} -oL -eL {cmdi}"
                        sub_cmds.append(f'echo "===== [Bactopia Tool] {tool} =====" ; {cmdi}')
                    full_cmd = " ; ".join(sub_cmds)
                    status_box_tools.info("Executando Tools (async).")
                    start_async_runner_ns(full_cmd, "tools")

if st.session_state.get("tools_running", False):
    drain_log_queue_ns("tools", tail_limit=500, max_pull=800)
    render_log_box_ns("tools", height=520)
    finished = check_status_and_finalize_ns("tools", status_box_tools)
    if not finished:
        time.sleep(0.3)
        _st_rerun()
else:
    render_log_box_ns("tools", height=520)

# ==================== MobSuite plasmids extraction UI ======================
st.divider()
st.subheader("MobSuite — extração organizada de plasmídeos (FASTA)")

st.caption(
    "Este utilitário copia os arquivos `plasmid_*.fasta` / `plasmid_*.fasta.gz` "
    "de cada amostra (em `tools/mobsuite`) para uma pasta organizada por amostra."
)

selected_samples = st.session_state.get("bt_selected_samples", []) or []

default_dest = ""
if bt_outdir:
    default_dest = os.path.join(bt_outdir, "plasmids_mobsuite")

col_m1, col_m2 = st.columns([2, 1])
with col_m1:
    mobsuite_dest = st.text_input(
        "Pasta de destino",
        value=st.session_state.get("bt_mobsuite_dest", default_dest),
        key="bt_mobsuite_dest",
        help="Será criada se não existir. Dentro dela haverá uma subpasta por amostra.",
    )
with col_m2:
    mobsuite_decompress = st.checkbox(
        "Descompactar .gz para .fasta",
        value=st.session_state.get("bt_mobsuite_decompress", False),
        key="bt_mobsuite_decompress",
        help="Se marcado, arquivos .fasta.gz serão descompactados para .fasta.",
    )

btn_extract_mobsuite = st.button(
    "📂 Extrair plasmídeos do MobSuite",
    disabled=not bt_outdir or not selected_samples,
)

if not bt_outdir:
    st.info("Defina a *Pasta de resultados do Bactopia* acima para habilitar a extração.")
elif not selected_samples:
    st.info("Selecione ao menos uma amostra para extrair os plasmídeos.")

if btn_extract_mobsuite:
    with st.spinner("Extraindo plasmídeos do MobSuite..."):
        n_samp, n_files, logs = extract_mobsuite_plasmids(
            bt_outdir=bt_outdir,
            samples=selected_samples,
            dest_root=mobsuite_dest or None,
            decompress_gz=mobsuite_decompress,
        )

    if n_files > 0:
        st.success(f"Extração concluída: {n_samp} amostras processadas, {n_files} arquivos gerados/copiedos.")
    else:
        st.warning("Nenhum arquivo de plasmídeo foi encontrado/extraído. Veja o log abaixo.")

    st.text_area(
        "Log da extração (MobSuite)",
        value="\n".join(logs) if logs else "Sem mensagens.",
        height=200,
    )

# ========================= merged-results =========================
st.divider()
st.subheader("merged-results (runs recentes)")
runs_root = pathlib.Path(bt_outdir) / "bactopia-runs" if bt_outdir else None
if runs_root and runs_root.exists():
    runs = sorted(runs_root.glob("*"))
    if runs:
        latest = runs[-1]
        mr = latest / "merged-results"
        if mr.exists():
            for f in sorted(mr.glob("*.tsv")):
                st.markdown(f"- `{f.name}` — {f}")
        else:
            st.caption("Nenhum merged-results encontrado neste run.")
    else:
        st.caption("Ainda não há runs em bactopia-runs.")
else:
    st.caption("Diretório bactopia-runs não encontrado.")
