# PORT.py — Bactopia UI Local (PORT via Nextflow)
# ----------------------------------------------------------------------
# Uso: como página do app (ex.: pages/PORT.py) ou script separado
# Requisitos: streamlit>=1.30; Nextflow + (Docker/Apptainer); PORT clonado
# ----------------------------------------------------------------------

"""
PORT Interface.

This module provides a UI for running PORT (Plasmid Outbreak Research Tool).
It supports:
1.  **Input Modes**: Running on raw Nanopore FASTQs or existing Bactopia assemblies.
2.  **Assembly Management**: Automatically creating a `port_assemblies` directory
    symlinked/copied from Bactopia output.
3.  **Configuration**: Setting assemblers, read types, and resource limits.
4.  **Execution**: Asynchronous running of the PORT Nextflow pipeline.
"""

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
import gzip
from typing import List
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components
# ============================= Config geral =============================
st.set_page_config(page_title="BEAR-HUB", page_icon="🐻", layout="wide")

APP_ROOT = pathlib.Path(__file__).resolve().parent
PAGES_DIR = APP_ROOT / "pages"
PAGE_BACTOPIA = PAGES_DIR / "BACTOPIA.py"
PAGE_TOOLS = PAGES_DIR / "BACTOPIA-TOOLS.py"
PAGE_PORT = PAGES_DIR / "PORT.py"
PAGE_TEST = PAGES_DIR / "TEST.py"

# APP_ROOT já existe e é o diretório deste arquivo
# descobrimos a raiz do projeto de forma segura
if (APP_ROOT / "static").is_dir():
    PROJECT_ROOT = APP_ROOT
elif (APP_ROOT.parent / "static").is_dir():
    PROJECT_ROOT = APP_ROOT.parent
else:
    PROJECT_ROOT = APP_ROOT  # fallback



# ============================= Config =============================
# Deixe o set_page_config no app principal, se estiver usando multipage.
# st.set_page_config(page_title="PORT — Nanopore & Plasmídeos", layout="wide")

def _st_rerun():
    """Trigger a Streamlit rerun."""
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()

APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
DEFAULT_BACTOPIA_OUTDIR = str((pathlib.Path.cwd() / "bactopia_out").resolve())
DEFAULT_PORT_OUTDIR = str((pathlib.Path.cwd() / "port_out").resolve())

# ============================= Utils comuns (mesmo estilo BACTOPIA-TOOLS) =============================
def ensure_state_dir():
    """Ensure state directory exists."""
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)

def which(cmd: str):
    """Find command in PATH."""
    from shutil import which as _which
    return _which(cmd)

def nextflow_available():
    """Check if Nextflow is available."""
    return which("nextflow") is not None

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def _strip_ansi(s: str) -> str:
    """Strip ANSI codes."""
    return ANSI_ESCAPE.sub("", s)

def _normalize_linebreaks(chunk: str) -> list[str]:
    """
    Normalize log output:
      - remove ANSI color/escape codes
      - adapt long lines into more readable breaks
    """
    if not chunk:
        return []
    chunk = _strip_ansi(chunk).replace("\r", "\n")
    # alguns ajustes para quebrar melhor as linhas longas
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    return [p.rstrip() for p in chunk.split("\n") if p.strip() != ""]

async def _async_read_stream(stream, log_q: Queue, stop_event: threading.Event):
    """Async stream reader."""
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
    """Async command executor."""
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
    """Thread entry point."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_exec(full_cmd, log_q, status_q, stop_event))
    finally:
        loop.close()

def start_async_runner_ns(full_cmd: str, ns: str):
    """Start async runner thread."""
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
    """Request stop of async runner."""
    ev = st.session_state.get(f"{ns}_stop_event")
    if ev and not ev.is_set():
        ev.set()

def drain_log_queue_ns(ns: str, tail_limit: int = 200, max_pull: int = 500):
    """Drain log queue into session state."""
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
    """Render log box."""
    lines = st.session_state.get(f"{ns}_live_log", [])
    content = html.escape("\n".join(lines)) if lines else ""
    components.html(
        f"""
    <div id="logbox_{ns}" style="
        width:100%; height:{height-40}px; margin:0 auto; padding:12px;
        overflow-y:auto; overflow-x:auto; background:#0b0b0b; color:#e6e6e6;
        border-radius:10px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
        font-size:13px; line-height:1.35;">
      <pre style="margin:0; white-space: pre;">{content or "&nbsp;"}</pre>
    </div>
    <script>
      const el = document.getElementById("logbox_{ns}");
      if (el) {{ el.scrollTop = el.scrollHeight; }}
    </script>
    """,
        height=height,
        scrolling=False,
    )

def check_status_and_finalize_ns(ns: str, status_box):
    """Check run status and update UI."""
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

# ============================= Funções PORT / Bactopia =============================

def extract_sample_id_from_filename(path: pathlib.Path) -> str:
    """
    Extract sample ID from a FASTA filename.

    Args:
        path (pathlib.Path): Path to the file.

    Returns:
        str: Sample ID (filename without extension).
    """
    name = path.name
    for ext in (".fa.gz", ".fna.gz", ".fasta.gz", ".fa", ".fna", ".fasta"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    if "." in name:
        name = name.split(".", 1)[0]
    return name

def scan_bactopia_assemblies(bactopia_run_dir: str):
    """
    Scan Bactopia output for assembly files.

    Args:
        bactopia_run_dir (str): Path to Bactopia output.

    Returns:
        dict: Mapping of sample_id to list of assembly file paths.
    """
    run_path = pathlib.Path(bactopia_run_dir).expanduser().resolve()
    if not run_path.exists():
        return {}

    sample_map = {}
    patterns = ("*.fa", "*.fna", "*.fasta", "*.fa.gz", "*.fna.gz", "*.fasta.gz")
    for pattern in patterns:
        for f in run_path.rglob(pattern):
            if "port_assemblies" in f.parts:
                continue
            sid = extract_sample_id_from_filename(f)
            sample_map.setdefault(sid, []).append(f)
    return sample_map

def _base_name_without_double_ext(path: pathlib.Path) -> str:
    """
    Get filename without any FASTA extension.

    Args:
        path (pathlib.Path): File path.

    Returns:
        str: Base name.
    """
    name = path.name
    for ext in (".fa.gz", ".fna.gz", ".fasta.gz", ".fa", ".fna", ".fasta"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return path.stem

def build_port_assemblies_from_sample_map(bactopia_run_dir: str, sample_map, selected_samples):
    """
    Prepare the `port_assemblies` directory.

    Creates a directory `port_assemblies` inside the run directory and populates
    it with symlinks (or uncompressed copies) of the selected samples' assemblies.

    Args:
        bactopia_run_dir (str): Bactopia run directory.
        sample_map (dict): Mapping of sample IDs to files.
        selected_samples (list): List of selected sample IDs.

    Returns:
        tuple: (target_path, count_created)
    """
    run_path = pathlib.Path(bactopia_run_dir).expanduser().resolve()
    target = run_path / "port_assemblies"
    target.mkdir(parents=True, exist_ok=True)

    # Limpa tudo dentro da pasta
    for item in list(target.iterdir()):
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
        except Exception:
            pass

    created = 0

    for sid in selected_samples:
        files = sample_map.get(sid, [])
        for f in files:
            core = _base_name_without_double_ext(f)
            out_name = f"{sid}__{core}.fasta"
            out_path = target / out_name
            if out_path.exists():
                continue

            src_str = str(f)
            lower = src_str.lower()

            # Comprimido -> descompacta para .fasta
            if lower.endswith((".fa.gz", ".fna.gz", ".fasta.gz")):
                try:
                    with gzip.open(src_str, "rb") as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    created += 1
                except Exception as e:
                    q = st.session_state.get("port_log_q")
                    if q:
                        q.put(f"[PORT] Erro ao descompactar {f} -> {out_path}: {e}")

            # Não comprimido -> symlink .fasta
            elif lower.endswith((".fa", ".fna", ".fasta")):
                try:
                    os.symlink(f, out_path)
                    created += 1
                except Exception as e:
                    q = st.session_state.get("port_log_q")
                    if q:
                        q.put(f"[PORT] Não foi possível criar symlink {out_path} -> {f}: {e}")

            else:
                q = st.session_state.get("port_log_q")
                if q:
                    q.put(f"[PORT] Ignorando arquivo com extensão não reconhecida: {f}")

    return target, created

# ============================= Página PORT =============================

st.title("PORT — Montagem Nanopore & Tipagem de Plasmídeos (EM CONSTRUÇÃO)")

st.markdown(
    """
Esta página integra o **PORT** ao Bactopia-UI:

- Rodar o PORT com **FASTQs Nanopore** (`--input_dir`)
- Rodar o PORT usando **assemblies do Bactopia por amostra** (`--assemblies`),  
  montando a pasta `port_assemblies/` automaticamente a partir do `bactopia_out`.
"""
)

# ----------------- Configuração geral -----------------
st.subheader("Configuração geral do PORT")

col_cfg1, col_cfg2 = st.columns([2, 1])

with col_cfg1:
    main_nf_path = st.text_input(
        "Caminho para o main.nf do PORT",
        value=st.session_state.get("port_main_nf", "/mnt/HD/PORT/PORT/main.nf"),
        key="port_main_nf",
        help="Ex.: /mnt/HD/PORT/PORT/main.nf ou caminho relativo."
    ).strip()
    if not main_nf_path:
        main_nf_path = "main.nf"

    exec_mode = st.selectbox(
        "Ambiente de execução",
        options=["Docker (padrão / profile standard)", "Conda (profile conda)"],
        index=0,
        key="port_exec_mode",
    )

    # --- Escolha do tipo de entrada ---
    input_mode = st.radio(
        "Tipo de entrada",
        options=["FASTQs Nanopore (reads próprios)", "Assemblies do Bactopia (por amostra)"],
        index=1,
        key="port_input_mode",
    )

    input_dir = ""
    assemblies_dir = ""

    if input_mode.startswith("FASTQ"):
        input_dir = st.text_input(
            "Diretório com FASTQs (Nanopore) — --input_dir",
            value=st.session_state.get("port_input_dir", "input"),
            key="port_input_dir",
            help="Diretório que será passado para --input_dir (todos os FASTQ/FASTQ.GZ)."
        ).strip()
    else:
        # usamos uma chave interna que NÃO é key de widget,
        # para evitar conflito com outras páginas
        asm_state_key = "port_assemblies_path"
        if asm_state_key not in st.session_state:
            st.session_state[asm_state_key] = ""

        assemblies_default = st.session_state[asm_state_key]

        # Diretório onde o PORT vai ler os .fasta finais
        assemblies_dir = st.text_input(
            "Diretório de assemblies para o PORT — --assemblies",
            value=assemblies_default,
            help="Diretório com .fasta (pasta port_assemblies gerada abaixo)."
        ).strip()

        # Mantém o valor atualizado no session_state interno
        st.session_state[asm_state_key] = assemblies_dir

        with st.expander("Montar pasta 'port_assemblies' a partir do bactopia_out (por amostra)", expanded=True):
            bactopia_run_dir = st.text_input(
                "Pasta de resultados do Bactopia (bactopia_out)",
                value=st.session_state.get("port_bactopia_outdir", DEFAULT_BACTOPIA_OUTDIR),
                key="port_bactopia_outdir",
                help="Pasta raiz do bactopia_out. O app vai procurar FASTA recursivamente e agrupar por amostra."
            ).strip()

            sample_map = {}
            if bactopia_run_dir:
                last_dir = st.session_state.get("port_last_bactopia_dir")
                if last_dir != bactopia_run_dir or not st.session_state.get("port_bactopia_samples"):
                    sample_map = scan_bactopia_assemblies(bactopia_run_dir)
                    st.session_state["port_last_bactopia_dir"] = bactopia_run_dir
                    st.session_state["port_bactopia_samples"] = sample_map
                else:
                    sample_map = st.session_state["port_bactopia_samples"]

            if sample_map:
                total_samples = len(sample_map)
                total_files = sum(len(v) for v in sample_map.values())
                st.info(
                    f"Foram encontradas **{total_samples} amostras** e "
                    f"**{total_files} arquivos FASTA/FA (.fa/.fna/.fasta/.gz)**."
                )

                sample_ids = sorted(sample_map.keys())
                default_sel = st.session_state.get("port_selected_samples") or sample_ids
                selected_samples = st.multiselect(
                    "Selecione as amostras que serão input do PORT",
                    options=sample_ids,
                    default=default_sel,
                    key="port_selected_samples",
                    help="IDs de amostra inferidos dos nomes dos FASTA (mesmo identificador lógico que o Bactopia Tools usa)."
                )

                if st.button("Criar/atualizar pasta 'port_assemblies'"):
                    if not selected_samples:
                        st.error("Selecione pelo menos uma amostra.")
                    else:
                        target, created = build_port_assemblies_from_sample_map(
                            bactopia_run_dir,
                            sample_map,
                            selected_samples
                        )
                        # Atualiza somente a chave interna (não é key de widget)
                        st.session_state[asm_state_key] = str(target)
                        assemblies_dir = str(target)
                        st.success(
                            f"Pasta **{target}** atualizada.\n\n"
                            f"Foram criados **{created} arquivos .fasta** "
                            f"(descompactados ou linkados). Nenhum .gz é usado pelo PORT."
                        )
            else:
                if bactopia_run_dir:
                    st.warning("Nenhum FASTA (.fa/.fna/.fasta/.gz) encontrado nesse bactopia_out.")
                else:
                    st.info("Informe a pasta do bactopia_out para detectar as amostras.")

    # --- Diretório de saída do PORT ---
    output_dir = st.text_input(
        "Diretório de saída do PORT — --output_dir",
        value=st.session_state.get("port_outdir", DEFAULT_PORT_OUTDIR),
        key="port_outdir",
        help="Resultados do PORT serão escritos aqui."
    ).strip()

    # --- Parâmetros de montagem ---
    st.markdown("### Parâmetros de montagem")

    assembler = st.selectbox(
        "Assembler (--assembler)",
        options=["autocycler", "dragonflye"],
        index=0,
        key="port_assembler",
        help="Conforme documentação do PORT."
    )

    read_type = st.text_input(
        "Read type (--read_type)",
        value=st.session_state.get("port_read_type", "ont_r10"),
        key="port_read_type",
        help="Ex.: ont_r9, ont_r10. Usado principalmente nas etapas de Medaka."
    ).strip()

    medaka_model = st.text_input(
        "Medaka model (--medaka_model)",
        value=st.session_state.get("port_medaka_model", "r1041_e82_400bps_sup"),
        key="port_medaka_model",
        help="Modelo de Medaka para polimento (especialmente relevante para dragonflye)."
    ).strip()

    st.markdown("### Recursos globais do Nextflow")

    c_res1, c_res2 = st.columns(2)
    with c_res1:
        max_cpus = st.number_input(
            "--max_cpus",
            min_value=1,
            max_value=min(os.cpu_count() or 64, 256),
            value=16,
            step=1,
            key="port_max_cpus",
        )
    with c_res2:
        max_memory = st.text_input(
            "--max_memory",
            value=st.session_state.get("port_max_memory", "64.GB"),
            key="port_max_memory",
            help="Ex.: 32.GB, 64.GB, 128.GB."
        ).strip()

with col_cfg2:
    st.subheader("Execução & Log")

    status_box_port = st.empty()

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        start_port = st.button(
            "▶️ Iniciar PORT",
            key="btn_port_start",
            disabled=st.session_state.get("port_running", False),
        )
    with c_btn2:
        stop_port = st.button(
            "⏹️ Interromper",
            key="btn_port_stop",
            disabled=not st.session_state.get("port_running", False),
        )

    if stop_port:
        request_stop_ns("port")
        status_box_port.warning("Solicitada interrupção…")

# ----------------- Montagem do comando Nextflow -----------------
cmd_parts = ["nextflow", "run", main_nf_path]

if input_mode.startswith("FASTQ"):
    if input_dir:
        cmd_parts += ["--input_dir", input_dir]
else:
    if assemblies_dir:
        cmd_parts += ["--assemblies", assemblies_dir]

if output_dir:
    cmd_parts += ["--output_dir", output_dir]

cmd_parts += ["--assembler", assembler]

if read_type:
    cmd_parts += ["--read_type", read_type]
if medaka_model:
    cmd_parts += ["--medaka_model", medaka_model]

# profile / conda
if exec_mode.startswith("Conda"):
    cmd_parts += ["-profile", "conda"]
    conda_env = st.session_state.get("port_conda_env", "")
    conda_env = st.text_input(
        "Nome do ambiente Conda (--conda_env, opcional)",
        value=conda_env,
        key="port_conda_env",
        help="Se deixado em branco, o profile conda usará o env padrão do pipeline."
    ).strip()
    if conda_env:
        cmd_parts += ["--conda_env", conda_env]

# Recursos globais
if max_cpus:
    cmd_parts += ["--max_cpus", str(max_cpus)]
if max_memory:
    cmd_parts += ["--max_memory", max_memory]

cmd_parts.append("-resume")

cmd_preview = " ".join(shlex.quote(x) for x in cmd_parts)

st.markdown("#### Comando Nextflow (pré-visualização)")
st.code(cmd_preview, language="bash")

# ----------------- Disparo da execução (async, estilo Tools) -----------------
if start_port:
    if not nextflow_available():
        status_box_port.error("Nextflow não encontrado no PATH.")
    elif input_mode.startswith("FASTQ") and not input_dir:
        status_box_port.error("Informe o diretório com FASTQs para --input_dir.")
    elif (not input_mode.startswith("FASTQ")) and not assemblies_dir:
        status_box_port.error(
            "Informe o diretório de assemblies para --assemblies "
            "(ou gere a pasta port_assemblies primeiro)."
        )
    else:
        stdbuf = shutil.which("stdbuf")
        full_cmd = cmd_preview
        if stdbuf:
            full_cmd = f"{stdbuf} -oL -eL {cmd_preview}"
        status_box_port.info("Executando PORT (async).")
        start_async_runner_ns(full_cmd, "port")

# ----------------- Log em tempo real -----------------
st.markdown("---")
st.subheader("Saída do Nextflow (PORT)")

if st.session_state.get("port_running", False):
    drain_log_queue_ns("port", tail_limit=500, max_pull=800)
    render_log_box_ns("port", height=520)
    finished = check_status_and_finalize_ns("port", status_box_port)
    if not finished:
        time.sleep(0.3)
        _st_rerun()
else:
    render_log_box_ns("port", height=520)
