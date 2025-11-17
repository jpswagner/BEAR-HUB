# app_bactopia_main.py — Bactopia UI Local (FOFN-first, multi-amostras)
# ---------------------------------------------------------------------
# • Interface Streamlit para orquestrar Bactopia (via Nextflow) SOMENTE via FOFN
# • Gerador de FOFN com detecção automática de runtype:
#     - paired-end (R1/R2)
#     - single-end (SE)
#     - ont (long reads)
#     - hybrid (PE + ONT na mesma amostra)
#     - assembly (FASTA)
# • Sem “amostra única” (toda execução via --samples)
# • Mantidos apenas --max_cpus e --max_memory (removidos -name e -work-dir)
# • Validação pré-execução, execução assíncrona com tail dos logs, limpeza de execuções
# • Relatórios Nextflow opcionais (-with-report/-with-timeline/-with-trace)
# ---------------------------------------------------------------------

import os
import shlex
import time
import yaml
import pathlib
import subprocess
import re
import shutil
import asyncio
import html
import threading
import fnmatch
import hashlib
from typing import List, Dict, Tuple
from queue import Queue, Empty

import streamlit as st
import streamlit.components.v1 as components

# ============================= Config inicial =============================
st.set_page_config(page_title="Bactopia UI", layout="wide")

def _st_rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn: fn()

APP_STATE_DIR = pathlib.Path.home() / ".bactopia_ui_local"
PRESETS_FILE = APP_STATE_DIR / "presets.yaml"
DEFAULT_PRESET_NAME = "default"

DEFAULT_OUTDIR = str((pathlib.Path.cwd() / "bactopia_out").resolve())
st.session_state.setdefault("outdir", DEFAULT_OUTDIR)

# ============================= Utils =============================

def ensure_state_dir():
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)

def which(cmd: str):
    from shutil import which as _which
    return _which(cmd)

def docker_available():
    return which("docker") is not None

def singularity_available():
    return which("singularity") is not None or which("apptainer") is not None

def nextflow_available():
    return which("nextflow") is not None

def run_cmd(cmd: str | List[str], cwd: str | None = None) -> tuple[int, str, str]:
    if isinstance(cmd, list): shell_cmd = " ".join(shlex.quote(x) for x in cmd)
    else: shell_cmd = cmd
    try:
        res = subprocess.run(["bash","-lc", shell_cmd], cwd=cwd, text=True,
                             capture_output=True, check=False)
        return res.returncode, res.stdout or "", res.stderr or ""
    except Exception as e:
        return 1, "", f"Falha ao executar: {e}"

# ============================= Presets =============================

PRESET_KEYS_ALLOWLIST = {
    # Execução
    "profile","outdir","datasets","resume","threads","memory_gb",
    # FOFN generator
    "fofn_base","fofn_recursive","fofn_species","fofn_gsize","fofn_use",
    "fofn_long_reads","fofn_infer_ont_by_name","fofn_merge_multi","fofn_include_assemblies",
    # Ferramentas
    "fastp_mode","fastp_dash3","fastp_M","fastp_W","fastp_opts_text",
    "fastp_enable_5prime","fastp_q_enable","fastp_q","fastp_l_enable","fastp_l",
    "fastp_n","fastp_u","fastp_cut_front","fastp_cut_tail","fastp_cut_meanq","fastp_cut_win",
    "fastp_detect_adapter_pe","fastp_poly_g","fastp_extra",
    # Unicycler
    "unicycler_mode","unicycler_min_len","unicycler_extra",
    # Params extras e relatórios
    "extra_params","with_report","with_timeline","with_trace",
}

def load_presets():
    ensure_state_dir()
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def save_presets(presets: dict):
    ensure_state_dir()
    with open(PRESETS_FILE, "w", encoding="utf-8") as fh:
        yaml.safe_dump(presets, fh, sort_keys=True, allow_unicode=True)

def _snapshot_current_state() -> dict:
    snap = {}
    for k in PRESET_KEYS_ALLOWLIST:
        if k in st.session_state:
            snap[k] = st.session_state[k]
    return snap

def _apply_dict_to_state(values: dict):
    for k, v in (values or {}).items():
        if k in PRESET_KEYS_ALLOWLIST:
            st.session_state[k] = v

def apply_preset_before_widgets():
    pending = st.session_state.pop("__pending_preset_values", None)
    if pending:
        _apply_dict_to_state(pending)
        st.session_state["__preset_msg"] = st.session_state.get("__preset_msg") or "Preset aplicado."

def _cb_stage_apply_preset():
    name = st.session_state.get("__preset_to_load")
    if not name or name == "(nenhum)": return
    presets = load_presets()
    st.session_state["__pending_preset_values"] = presets.get(name, {})
    st.session_state["__preset_msg"] = f"Preset preparado: {name} (aplicado neste reload)"

def _cb_save_preset():
    name = (st.session_state.get("__preset_save_name") or "").strip() or DEFAULT_PRESET_NAME
    name = re.sub(r"\s+", "_", name)
    presets = load_presets()
    presets[name] = _snapshot_current_state()
    save_presets(presets)
    st.session_state["__preset_msg"] = f"Preset salvo: {name}"

def _cb_delete_preset():
    name = st.session_state.get("__preset_to_load")
    if not name or name == "(nenhum)": return
    presets = load_presets()
    if name in presets:
        del presets[name]
        save_presets(presets)
        st.session_state["__preset_msg"] = f"Preset excluído: {name}"

def render_presets_sidebar():
    st.header("Presets")
    presets = load_presets()
    names = sorted(presets.keys())
    st.selectbox("Carregar preset", ["(nenhum)"] + names, key="__preset_to_load")
    st.text_input("Salvar como (nome do preset)", key="__preset_save_name", placeholder="ex.: meu_preset")
    st.markdown('<div id="presets-section">', unsafe_allow_html=True)
    st.button("Aplicar", key="__btn_apply", on_click=_cb_stage_apply_preset, use_container_width=True)
    st.button("Salvar atual", key="__btn_save", on_click=_cb_save_preset, use_container_width=True)
    st.button("Excluir", key="__btn_delete", on_click=_cb_delete_preset, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.get("__preset_msg"):
        st.caption(st.session_state["__preset_msg"])

apply_preset_before_widgets()

# ============================= Explorador (inline + pop-up) =============================

def _safe_id(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]

def _list_dir(cur: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    try:
        entries = list(cur.iterdir())
    except Exception:
        entries = []
    dirs  = [p for p in entries if p.is_dir()]
    files = [p for p in entries if p.is_file()]
    dirs.sort(key=lambda p: p.name.lower())
    files.sort(key=lambda p: p.name.lower())
    return dirs, files

def _fs_browser_core(label: str, key: str, mode: str = "file",
                     start: str | None = None, patterns: list[str] | None = None):
    base_start = start or st.session_state.get(key) or os.getcwd()
    cur_key = f"__picker_cur__{key}"
    try:
        cur = pathlib.Path(st.session_state.get(cur_key, base_start)).expanduser().resolve()
    except Exception:
        cur = pathlib.Path(base_start).expanduser().resolve()

    def set_cur(p: pathlib.Path):
        st.session_state[cur_key] = str(p.expanduser().resolve())

    c_up, c_home, c_path, c_pick = st.columns([0.9,0.9,6,2])
    with c_up:
        if st.button("⬆️ Subir", key=f"{key}_up"):
            parent = cur.parent if cur.parent != cur else cur
            set_cur(parent); _st_rerun()
    with c_home:
        if st.button("🏠 Home", key=f"{key}_home"):
            set_cur(pathlib.Path.home()); _st_rerun()
    with c_path:
        st.caption(str(cur))
    with c_pick:
        if mode == "dir":
            if st.button("Escolher", key=f"{key}_choose_dir"):
                st.session_state[key] = str(cur)

    dirs, files = _list_dir(cur)
    st.markdown("**Pastas**")
    dcols = st.columns(2)
    for i, d in enumerate(dirs):
        did = _safe_id(str(d))
        if dcols[i % 2].button("📁 " + d.name, key=f"{key}_d_{did}"):
            set_cur(d); _st_rerun()

    if mode == "file":
        if patterns:
            files = [f for f in files if any(fnmatch.fnmatch(f.name, pat) for pat in patterns)]
        st.markdown("**Arquivos**")
        for f in files:
            fid = _safe_id(str(f))
            if st.button("📄 " + f.name, key=f"{key}_f_{fid}"):
                st.session_state[key] = str(f.resolve())
                st.session_state[f"__open_{key}"] = False
                _st_rerun()

def path_picker(label: str, key: str, mode: str = "dir",
                start: str | None = None, patterns: list[str] | None = None, help: str | None = None):
    col1, col2 = st.columns([7,2])
    with col1:
        val = st.text_input(label, value=st.session_state.get(key, start or ""), key=key, help=help)
        try:
            if val:
                val_abs = str(pathlib.Path(val).expanduser().resolve())
                if val_abs != val:
                    st.session_state[key] = val_abs
        except Exception:
            pass
    with col2:
        if st.button("Explorar…", key=f"open_{key}", use_container_width=True):
            st.session_state[f"__open_{key}"] = True
            try:
                hint = pathlib.Path(st.session_state.get(key) or start or os.getcwd())
                st.session_state[f"__picker_cur__{key}"] = str((hint if hint.is_dir() else hint.parent).expanduser().resolve())
            except Exception:
                st.session_state[f"__picker_cur__{key}"] = str(pathlib.Path(start or os.getcwd()).expanduser().resolve())

    if st.session_state.get(f"__open_{key}", False) and hasattr(st, "dialog"):
        @st.dialog(label, width="large")
        def _dlg():
            _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
            c_ok, c_cancel = st.columns(2)
            with c_ok:
                if st.button("✅ Usar este caminho", key=f"use_{key}"):
                    if mode == "dir":
                        cur = pathlib.Path(st.session_state.get(f"__picker_cur__{key}", start or os.getcwd()))
                        st.session_state[key] = str(cur.expanduser().resolve())
                    st.session_state[f"__open_{key}"] = False; _st_rerun()
            with c_cancel:
                if st.button("Cancelar", key=f"cancel_{key}"):
                    st.session_state[f"__open_{key}"] = False; _st_rerun()
        _dlg()
    elif st.session_state.get(f"__open_{key}", False):
        st.info(f"{label} (modo inline)")
        _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
        if st.button("✅ Usar este caminho", key=f"use_inline_{key}"):
            if mode == "dir":
                cur = pathlib.Path(st.session_state.get(f"__picker_cur__{key}", start or os.getcwd()))
                st.session_state[key] = str(cur.expanduser().resolve())
            st.session_state[f"__open_{key}"] = False; _st_rerun()

    return st.session_state.get(key) or ""

# ============================= Descoberta / FOFN =============================

FASTQ_PATTERNS = ["*.fastq.gz","*.fq.gz","*.fastq","*.fq"]
FA_PATTERNS    = ["*.fna.gz","*.fa.gz","*.fasta.gz","*.fna","*.fa","*.fasta"]

PE1_PATTERNS = [
    re.compile(r"^(?P<root>.+?)[._-](?:R?1|1|[Aa])(?:_[0-9]{3})?$", re.IGNORECASE),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_[Rr]1_\d{3}$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_1_\d{3}$"),
]
PE2_PATTERNS = [
    re.compile(r"^(?P<root>.+?)[._-](?:R?2|2|[Bb])(?:_[0-9]{3})?$", re.IGNORECASE),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_[Rr]2_\d{3}$"),
    re.compile(r"^(?P<root>.+?)_L\d{3,4}_2_\d{3}$"),
]
LANE_SUFFIX = re.compile(r"(_L\d{3,4})?(_\d{3})?$", re.IGNORECASE)

def _drop_exts(name: str) -> str:
    for ext in [".fastq.gz",".fq.gz",".fastq",".fq",".fna.gz",".fa.gz",".fasta.gz",".fna",".fa",".fasta"]:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name

def _infer_root_and_tag(path: pathlib.Path) -> Tuple[str, str]:
    # tag ∈ { 'PE1','PE2','SE' } (para FASTQ)
    name = _drop_exts(path.name)
    name = LANE_SUFFIX.sub("", name)
    for pat in PE1_PATTERNS:
        m = pat.match(name)
        if m:
            return m.group("root"), "PE1"
    for pat in PE2_PATTERNS:
        m = pat.match(name)
        if m:
            return m.group("root"), "PE2"
    return name, "SE"

def _is_probably_ont(p: pathlib.Path) -> bool:
    s = str(p.as_posix()).lower()
    return any(x in s for x in ["ont","nanopore","minion","promethion","fastq_pass","guppy"])

def _collect_files(base: pathlib.Path, patterns: List[str], recursive: bool) -> List[pathlib.Path]:
    out: List[pathlib.Path] = []
    for pat in patterns:
        out += list(base.rglob(pat) if recursive else base.glob(pat))
    # normaliza e ordena
    clean = []
    for p in out:
        try:
            if p.is_file():
                clean.append(p.resolve())
        except Exception:
            pass
    return sorted(set(clean))

def discover_runs_and_build_fofn(base_dir: str,
                                 recursive: bool,
                                 species: str,
                                 gsize: str,
                                 fofn_path: str,
                                 treat_se_as_ont: bool,
                                 infer_ont_by_name: bool,
                                 merge_multi: bool,
                                 include_assemblies: bool) -> dict:
    base = pathlib.Path(base_dir or ".")
    if not base.exists():
        raise FileNotFoundError("Pasta base não existe.")

    # garante outdir do FOFN
    fofn_parent = pathlib.Path(fofn_path).parent
    fofn_parent.mkdir(parents=True, exist_ok=True)

    fq_files = _collect_files(base, FASTQ_PATTERNS, recursive)
    fa_files = _collect_files(base, FA_PATTERNS, recursive) if include_assemblies else []

    # { sample: { 'pe1':[], 'pe2':[], 'se':[], 'ont':[], 'assembly':[] } }
    groups: Dict[str, Dict[str, List[str]]] = {}
    issues: List[str] = []

    for fq in fq_files:
        root, tag = _infer_root_and_tag(fq)
        d = groups.setdefault(root, {"pe1":[], "pe2":[], "se":[], "ont":[], "assembly":[]})
        if tag == "PE1":
            d["pe1"].append(str(fq))
        elif tag == "PE2":
            d["pe2"].append(str(fq))
        else:
            if treat_se_as_ont or (infer_ont_by_name and _is_probably_ont(fq)):
                d["ont"].append(str(fq))
            else:
                d["se"].append(str(fq))

    for fa in fa_files:
        root = _drop_exts(fa.name)
        d = groups.setdefault(root, {"pe1":[], "pe2":[], "se":[], "ont":[], "assembly":[]})
        d["assembly"].append(str(fa))

    header = ["sample","runtype","genome_size","species","r1","r2","extra"]
    rows: List[List[str]] = []

    def _join_or_pick(paths: List[str]) -> str:
        if not paths: return ""
        if merge_multi:
            return ",".join(paths)
        try:
            return sorted(paths, key=lambda p: pathlib.Path(p).stat().st_size if pathlib.Path(p).exists() else 0, reverse=True)[0]
        except Exception:
            return paths[0]

    counts = {"paired-end":0, "single-end":0, "ont":0, "hybrid":0, "assembly":0}

    for sample, parts in sorted(groups.items()):
        pe1 = parts["pe1"]; pe2 = parts["pe2"]; se = parts["se"]; ont = parts["ont"]; fa = parts["assembly"]

        if pe1 and not pe2:
            issues.append(f"{sample}: R1 encontrado sem R2.")
        if pe2 and not pe1:
            issues.append(f"{sample}: R2 encontrado sem R1.")

        if fa and not (pe1 or pe2 or se or ont):
            runtype = "assembly"
            r1 = ""; r2 = ""; extra = _join_or_pick(fa)
        elif pe1 and pe2 and ont:
            runtype = "hybrid"
            r1 = _join_or_pick(pe1)
            r2 = _join_or_pick(pe2)
            extra = _join_or_pick(ont)
        elif pe1 and pe2:
            runtype = "paired-end"
            r1 = _join_or_pick(pe1)
            r2 = _join_or_pick(pe2)
            extra = ""
        elif ont and not (pe1 or pe2):
            runtype = "ont"
            r1 = _join_or_pick(ont)
            r2 = ""; extra = ""
        elif se and not (pe1 or pe2 or ont):
            runtype = "single-end"
            r1 = _join_or_pick(se)
            r2 = ""; extra = ""
        elif fa and (pe1 or pe2 or se or ont):
            issues.append(f"{sample}: FASTA e FASTQ presentes; ignorando assembly no FOFN (use somente um).")
            if pe1 and pe2 and ont:
                runtype = "hybrid"; r1 = _join_or_pick(pe1); r2 = _join_or_pick(pe2); extra = _join_or_pick(ont)
            elif pe1 and pe2:
                runtype = "paired-end"; r1 = _join_or_pick(pe1); r2 = _join_or_pick(pe2); extra = ""
            elif ont:
                runtype = "ont"; r1 = _join_or_pick(ont); r2 = ""; extra = ""
            else:
                runtype = "single-end"; r1 = _join_or_pick(se); r2 = ""; extra = ""
        else:
            issues.append(f"{sample}: não foi possível classificar (arquivos ausentes?).")
            continue

        counts[runtype] = counts.get(runtype, 0) + 1
        rows.append([sample, runtype, gsize, species, r1, r2, extra])

        for label, arr in [("PE1", pe1), ("PE2", pe2), ("ONT", ont), ("SE", se)]:
            if len(arr) > 1 and not merge_multi:
                issues.append(f"{sample}: múltiplos arquivos em {label}; usando o maior. Ative 'Mesclar' para concatenar por vírgula.")

    with open(fofn_path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(map(str, r)) + "\n")

    return {
        "rows": rows,
        "counts": counts,
        "issues": issues,
        "header": header,
        "fofn_path": fofn_path,
    }

# ============================= Runner Async =============================

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def _strip_ansi(s: str) -> str:
    return ANSI_ESCAPE.sub("", s)

def _normalize_linebreaks(chunk: str) -> list[str]:
    if not chunk: return []
    chunk = _strip_ansi(chunk).replace("\r","\n")
    chunk = re.sub(r"\s+-\s+\[", "\n[", chunk)
    chunk = re.sub(r"(?<!^)\s+(?=executor\s*>)", "\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"✔\s+(?=\[)", "✔\n", chunk)
    parts = [p.rstrip() for p in chunk.split("\n") if p.strip()!=""]
    return parts

async def _async_read_stream(stream, log_q: Queue, stop_event: threading.Event):
    while True:
        line = await stream.readline()
        if not line: break
        s = line.decode(errors="replace")
        for sub in _normalize_linebreaks(s): log_q.put(sub)
        if stop_event.is_set(): break

async def _async_exec(full_cmd: str, log_q: Queue, status_q: Queue, stop_event: threading.Event):
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash","-lc", full_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
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
                try: await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError: proc.kill()
            except ProcessLookupError:
                pass
            break
        if proc.returncode is not None: break
        await asyncio.sleep(0.1)
    try: await asyncio.gather(t_out, t_err)
    except Exception: pass
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
    log_q = Queue(); status_q = Queue(); stop_event = threading.Event()
    th = threading.Thread(target=_thread_entry, args=(full_cmd, log_q, status_q, stop_event), daemon=True)
    th.start()
    st.session_state[f"{ns}_running"] = True
    st.session_state[f"{ns}_log_q"] = log_q
    st.session_state[f"{ns}_status_q"] = status_q
    st.session_state[f"{ns}_stop_event"] = stop_event
    st.session_state[f"{ns}_thread"] = th
    st.session_state[f"{ns}_live_log"] = []

def request_stop_ns(ns: str):
    ev = st.session_state.get(f"{ns}_stop_event")
    if ev and not ev.is_set(): ev.set()

def drain_log_queue_ns(ns: str, tail_limit: int = 200, max_pull: int = 500):
    q: Queue = st.session_state.get(f"{ns}_log_q")
    if not q: return
    buf = st.session_state.get(f"{ns}_live_log", [])
    pulled = 0
    while pulled < max_pull:
        try: line = q.get_nowait()
        except Empty: break
        buf.append(line); pulled += 1
    if len(buf) > tail_limit: buf[:] = buf[-tail_limit:]
    st.session_state[f"{ns}_live_log"] = buf

def render_log_box_ns(ns: str, height: int = 560):
    lines = st.session_state.get(f"{ns}_live_log", [])
    content = html.escape("\n".join(lines)) if lines else ""
    components.html(f"""
    <div id="logbox_{ns}" style=
        "
        width:100%; height:{height-40}px; margin:0 auto; padding:12px;
        overflow-y:auto; overflow-x:auto; background:#0b0b0b; color:#e6e6e6;
        border-radius:10px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
        font-size:13px; line-height:1.35;">
      <pre style="margin:0; white-space: pre;">{content or "&nbsp;"}</pre>
    </div>
    <script>const el=document.getElementById("logbox_{ns}"); if(el){{el.scrollTop=el.scrollHeight;}}</script>
    """, height=height, scrolling=False)

def check_status_and_finalize_ns(outdir: str, ns: str, status_box, report_zone):
    sq: Queue = st.session_state.get(f"{ns}_status_q")
    if not sq: return False
    finalized = False; msg=None; rc=None
    try:
        while True:
            kind, payload = sq.get_nowait()
            if kind=="error": msg=payload; finalized=True; rc=-1
            elif kind=="rc": rc=int(payload); finalized=True
    except Empty:
        pass
    if finalized:
        st.session_state[f"{ns}_running"] = False
        st.session_state[f"{ns}_thread"] = None
        st.session_state[f"{ns}_stop_event"] = None
        if rc==0: status_box.success("Concluído com sucesso.")
        else: status_box.error(msg or f"Execução terminou com código {rc}. Veja o log abaixo.")
    return finalized

# ============================= Sidebar =============================
with st.sidebar:
    st.header("Ambiente")
    nf_ok = nextflow_available(); docker_ok = docker_available(); sing_ok = singularity_available()
    st.write(
        f"Nextflow: {'✅' if nf_ok else '❌'} | "
        f"Docker: {'✅' if docker_ok else '❌'} | "
        f"Singularity/Apptainer: {'✅' if sing_ok else '❌'}"
    )
    st.caption("Prefira perfis docker/singularity para isolar dependências.")
    st.divider()
    render_presets_sidebar()

st.markdown("""
<style>
[data-testid="stSidebar"] #presets-section,
[data-testid="stSidebar"] #presets-section .stElementContainer,
[data-testid="stSidebar"] #presets-section .stButton { width: 100% !important; }
[data-testid="stSidebar"] #presets-section .stButton > button {
  width: 100% !important; min-height: 42px !important; display: flex !important;
  align-items: center !important; justify-content: center !important; border-radius: 8px !important;
}
[data-testid="stSidebar"] #presets-section .stButton > button div[data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] #presets-section .stButton > button div[data-testid="stMarkdownContainer"] p {
  margin: 0 !important; white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
}
button[kind="secondary"] span, button[kind="secondary"] div { white-space: nowrap !important; }
</style>
""", unsafe_allow_html=True)

# ============================= Página =============================
st.title("🧬 Bactopia UI")

# ------------------------- FOFN (múltiplas amostras) -------------------------
FOFN_HELP_MD = r"""
# ℹ️ Gerador de FOFN — como funciona

O gerador lê uma **pasta base** e produz um `samples.txt` (FOFN) no formato esperado pelo Bactopia, detectando automaticamente o **runtype** de cada amostra: **paired-end**, **single-end**, **ont**, **hybrid** (PE + ONT) e **assembly**.

---

## 1) O que você informa
- **Pasta base** (opção de varredura recursiva).
- **species** e **genome_size** (usados literalmente nas colunas do FOFN).
- **Tratar SE como ONT** (equivalente a `--long_reads` do `bactopia prepare`).
- **Inferir ONT por nome** (heurística: `ont|nanopore|minion|promethion|fastq_pass|guppy`).
- **Mesclar múltiplos arquivos** por vírgula (lanes/splits na mesma categoria).
- **Incluir assemblies (FASTA)**.

---

## 2) O que o app procura
- **FASTQ**: `*.fastq.gz`, `*.fq.gz`, `*.fastq`, `*.fq`
- **FASTA** (se habilitado): `*.fna(.gz)`, `*.fa(.gz)`, `*.fasta(.gz)`

Os caminhos são normalizados, duplicatas removidas e a lista é ordenada.

---

## 3) Agrupamento por amostra e decisão do *runtype*
1. Remove extensões e sufixos de lane do final (`_L00X`, `_00X`) para extrair o **root** (nome da amostra).
2. Usa regex para separar **PE1 (R1)** e **PE2 (R2)**; o resto vira **SE**.
3. **SE → ONT** se:
   - “Tratar SE como ONT” estiver ligado; **ou**
   - “Inferir ONT por nome” detectar palavras-chave no caminho.
4. Prioridade de classificação por amostra:
   - **assembly**: existe *somente* FASTA → `runtype=assembly` (FASTA vai em `extra`).
   - **hybrid**: existe **PE1 + PE2 + ONT** → `r1=PE1`, `r2=PE2`, `extra=ONT`.
   - **paired-end**: existe **PE1 + PE2** (sem ONT).
   - **ont**: existe **ONT** (sem PE).
   - **single-end**: existe apenas **SE** (e não virou ONT).
   - **Conflito (FASTA + reads)**: assembly é **ignorado** e um aviso é registrado.

---

## 4) Múltiplos arquivos na mesma categoria
- **Mesclar ON** → os caminhos são concatenados **por vírgula** (ex.: vários lanes em `r1`).
- **Mesclar OFF** → o app escolhe **o maior arquivo** por categoria (e cria um **aviso**).

---

## 5) Saída (FOFN TSV)
Cabeçalho fixo:
sample runtype genome_size species r1 r2 extra

markdown
Copiar código

Exemplos:
- **paired-end**  
  `S1	paired-end	5e6	Ecoli	/.../S1_R1.fastq.gz	/.../S1_R2.fastq.gz	`
- **single-end**  
  `S2	single-end	5e6	Ecoli	/.../S2.fastq.gz			`
- **ont**  
  `S3	ont	5e6	Ecoli	/.../S3.fastq.gz			`
- **hybrid**  
  `S4	hybrid	5e6	Ecoli	/.../S4_R1.fastq.gz	/.../S4_R2.fastq.gz	/.../S4_ont.fastq.gz`
- **assembly**  
  `S5	assembly	5e6	Ecoli				/.../S5.fna.gz`

> Convenções: em **hybrid**, o(s) ONT vão em **`extra`**; em **assembly**, o FASTA vai em **`extra`**.

---

## 6) Resumo e avisos
A UI mostra:
- **Contagem por runtype** (paired-end, single-end, ont, hybrid, assembly).
- **Avisos** (issues) por amostra:  
  • R1 sem R2, R2 sem R1  
  • Múltiplos arquivos sem “Mesclar” (usando o maior)  
  • Assembly + reads (assembly ignorado)  
  • Amostra não classificada

---

## 7) Padrões de nome aceitos (essencial)
Reconhece variações comuns:
- **PE1 (R1)**: `*_R1*.fastq.gz`, `*._1.fastq.gz`, `*.A.fastq.gz`, e variantes com lane (`_L00X_R1_001`).
- **PE2 (R2)**: `*_R2*.fastq.gz`, `*._2.fastq.gz`, `*.B.fastq.gz`, e variantes com lane.
- **Sufixos de lane removidos do final**: `_L00X` e/ou `_00X`.

Se seus nomes diferem muito, ajuste as regex no código.

---

## 8) Uso no comando final
A execução **sempre injeta** `--samples <caminho/samples.txt>` nos parâmetros, centralizando a orquestração via FOFN.
"""

st.subheader("Gerar FOFN (múltiplas amostras)", help = FOFN_HELP_MD)
with st.expander("Gerar FOFN", expanded=False):

    base_dir = path_picker("Pasta base de FASTQs/FASTAs", key="fofn_base", mode="dir", start=str(pathlib.Path.cwd()))
    recursive = st.checkbox("Incluir subpastas", value=True, key="fofn_recursive")

    cA, cB, cC = st.columns(3)
    with cA:
        species_in = st.text_input("species (opcional)", value=st.session_state.get("fofn_species","UNKNOWN_SPECIES"), key="fofn_species")
    with cB:
        gsize_in = st.text_input("genome_size (opcional)", value=st.session_state.get("fofn_gsize","0"), key="fofn_gsize")
    with cC:
        st.checkbox("Incluir assemblies (FASTA)", value=True, key="fofn_include_assemblies")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox("Tratar SE como ONT (long reads)", value=False, key="fofn_long_reads",
                    help="Equivalente ao --long_reads do 'bactopia prepare'.")
    with c2:
        st.checkbox("Heurística: inferir ONT por nome (ont|nanopore|...)", value=True, key="fofn_infer_ont_by_name")
    with c3:
        st.checkbox("Mesclar múltiplos arquivos por vírgula", value=True, key="fofn_merge_multi",
                    help="Se desmarcado, será usado apenas o maior arquivo por categoria (PE1/PE2/ONT/SE).")

    fofn_out = str((pathlib.Path(st.session_state.get("outdir", DEFAULT_OUTDIR)) / "samples.txt").resolve())
    st.caption(f"FOFN será salvo/atualizado em: `{fofn_out}`")

if st.button("🔎 Escanear e montar FOFN", key="btn_scan_fofn"):
    try:
        res = discover_runs_and_build_fofn(
            base_dir=base_dir,
            recursive=recursive,
            species=species_in,
            gsize=gsize_in,
            fofn_path=fofn_out,
            treat_se_as_ont=st.session_state.get("fofn_long_reads", False),
            infer_ont_by_name=st.session_state.get("fofn_infer_ont_by_name", True),
            merge_multi=st.session_state.get("fofn_merge_multi", True),
            include_assemblies=st.session_state.get("fofn_include_assemblies", True),
        )
        st.success(f"FOFN salvo/atualizado: {res['fofn_path']}")
        try:
            import pandas as pd
            df = pd.DataFrame(res["rows"], columns=res["header"])
            st.dataframe(df.head(1000), use_container_width=True)
        except Exception:
            st.write("Total de linhas:", len(res["rows"]))
        st.info("Resumo de runtype: " + ", ".join([f"{k}={v}" for k,v in res["counts"].items()]))
        if res["issues"]:
            st.warning("Possíveis problemas detectados:")
            for msg in res["issues"]:
                st.markdown(f"- {msg}")
    except Exception as e:
        st.error(f"Falha ao gerar FOFN: {e}")

# Forçamos uso do FOFN no comando final
st.session_state["fofn_use"] = True

# ------------------------- Parâmetros principais (sem amostra única) -------------------------
st.subheader("Parâmetros principais")
with st.expander("Parâmetros globais", expanded=False):
    colA, colB = st.columns(2)
    with colA:
        profile  = st.selectbox("Profile", ["docker","singularity","standard"], index=0, key="profile")
        outdir   = path_picker("Outdir (raiz resultados)", key="outdir", mode="dir", start=DEFAULT_OUTDIR,
                            help="Pasta onde o Nextflow/Bactopia escreverá a saída.")
        datasets = path_picker("datasets/ (opcional)", key="datasets", mode="dir", start=str(pathlib.Path.home()))
    with colB:
        resume     = st.checkbox("-resume (retomar)", value=True, key="resume")
        # Mantidos apenas estes recursos globais:
        max_cpus_default = min(os.cpu_count() or 64, 128)
        threads   = st.slider("--max_cpus", 0, max_cpus_default, 0, 1, key="threads")
        memory_gb = st.slider("--max_memory (GB)", 0, 256, 0, 1, key="memory_gb")

# ------------------------- fastp -------------------------
FASTP_HELP_MD = '''# ℹ️ fastp — ajuda dos parâmetros expostos na UI

Este painel monta a linha `--fastp_opts` usando flags do **fastp**, mantendo a semântica e defaults da documentação oficial.  
Se um campo **não** for marcado/preenchido, o app **não** envia aquela flag e o fastp usa o **default interno**.

---

## Corte por qualidade com janela deslizante
- **Ativar 5’ (`-5`, `--cut_front`)**  
  Varre da frente (5’) para a cauda; remove janelas cuja **média de qualidade** < limite e para quando a janela atende o critério. *Desligado por padrão no fastp*.  
  Usa os limites globais (**`-W`** e **`-M`**) salvo se sobrescrito por opções específicas de front (não expostas na UI).

- **Ativar 3’ (`-3`, `--cut_tail`)**  
  Varre da cauda (3’) para a frente; remove janelas com **média de qualidade** < limite e para quando atende o critério. *Desligado por padrão no fastp*.  
  Usa **`-W`** e **`-M`** (ou as variantes específicas de tail, não expostas na UI).

- **Tamanho da janela (`-W`, `--cut_window_size`)**  
  Tamanho (em bases) da janela compartilhada por `cut_front`/`cut_tail`. **Default fastp: 4**.

- **Qualidade média da janela (`-M`, `--cut_mean_quality`)**  
  Qualidade média mínima aceitada pela janela. **Default fastp: 20 (Q20)**.

> Dica: `-5` e `-3` são independentes. O fastp também tem `-r/--cut_right` (mais agressivo), não exposto na UI — use em **Extras** se precisar.

---

## Filtros de qualidade e comprimento
- **Qualidade base qualificada (`-q`, `--qualified_quality_phred`)**  
  Define o **phred mínimo** para uma base ser “qualificada”. **Default fastp: 15 (Q15)**.  
  > Se você **não** marcar este campo, o fastp ainda aplica o filtro de qualidade usando os seus defaults (a não ser que você desabilite com `-Q` via **Extras**).

- **Máx. % de bases não-qualificadas (`-u`, `--unqualified_percent_limit`)**  
  Percentual máximo de bases “não-qualificadas” permitido em um read; acima disso o read/pair é descartado. **Default fastp: 40%**.  
  > Se deixar **0** na UI, a flag **não** é enviada e o **default 40** do fastp prevalece.

- **Min length (`-l`, `--length_required`)**  
  Reads **mais curtos** que este valor são descartados. **Default fastp: 15**.  
  > Na UI, este filtro só é enviado se você marcar **“Min length (-l)”**.

- **Máx. Ns (`-n`, `--n_base_limit`)**  
  Se o número de bases **N** em um read excede o limite, o read/pair é descartado. **Default fastp: 5**.  
  > Se deixar **0** na UI, a flag **não** é enviada e o default **5** do fastp vale.

---

## Outras opções úteis
- **Detectar adaptador em PE (`--detect_adapter_for_pe`)**  
  Por padrão, a auto-detecção de adaptador é **apenas para SE**; esta flag habilita a detecção também em **paired-end** (mais lenta, porém encontra um pouco mais de adaptadores).

- **polyG (`-g`, `--trim_poly_g`)**  
  Força o corte de **caudas polyG** (comum em NextSeq/NovaSeq).  
  > O fastp habilita automaticamente polyG nesses equipamentos; `-g` **força** o recurso. É possível **desabilitar** com `-G` via **Extras**.

- **Cortes dirigidos (cut_*)**  
  Os campos **cut_mean_quality** e **cut_window_size** globais (**`-M`** e **`-W`**) são usados por `-5`/`-3`.  
  > O fastp possui variantes específicas por lado (ex.: `--cut_front_window_size`, `--cut_tail_mean_quality`), não expostas na UI. Use **Extras** se precisar refiná-las.

---

## Campo **Extras (append)**
Use para acrescentar qualquer flag suportada pelo fastp (ex.: `-r/--cut_right`, `-x/--trim_poly_x`, `-c/--correction`, `-Q`, `-G`, etc.).  
Digite exatamente como na CLI oficial; o conteúdo será **append** ao `--fastp_opts`.

---

## Defaults rápidos (se a UI não enviar a flag)
- `-W` **4**, `-M` **20 (Q20)**  
- `-q` **15 (Q15)**, `-u` **40%**, `-n` **5**, `-l` **15**  
- `-5`/`-3` **desligados** por padrão  
- polyG: auto-ativado em NextSeq/NovaSeq; `-g` força, `-G` desativa  
- Detecção de adaptador automática: **SE** por padrão; use `--detect_adapter_for_pe` para **PE**

---

## Observações
- Ativar `-5`/`-3` pode interferir com **deduplicação** baseada em posição (apenas relevante se você usar `--dedup`).  
- Se combinar várias flags em **Extras**, a **ordem** segue a linha final de comando gerada.

'''
st.subheader("Parâmetros FASTP/Unicycler", help= FASTP_HELP_MD)

with st.expander("Parâmetros do fastp", expanded=False):
    fastp_mode = st.radio("Modo", ["Simples (recomendado)", "Avançado (linha completa)"],
                          index=0, key="fastp_mode", horizontal=True)
    if fastp_mode.startswith("Simples"):
        topA, topB, topC = st.columns(3)
        with topA: st.checkbox("Ativar 3’ (-3)", value=True, key="fastp_dash3")
        with topB: st.slider("-M (média mínima da janela)", 0, 40, 20, 1, key="fastp_M")
        with topC: st.slider("-W (tamanho da janela)", 1, 50, 5, 1, key="fastp_W")

        st.markdown("**Opções adicionais (opcionais)**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.checkbox("Ativar 5’ (-5)", value=False, key="fastp_enable_5prime")
            st.checkbox("Detectar adaptador PE", value=False, key="fastp_detect_adapter_pe")
        with c2:
            st.checkbox("Qualidade (-q)", value=False, key="fastp_q_enable")
            if st.session_state.get("fastp_q_enable"):
                st.slider("Valor de -q", 0, 40, 20, 1, key="fastp_q")
        with c3:
            st.checkbox("Min length (-l)", value=False, key="fastp_l_enable")
            if st.session_state.get("fastp_l_enable"):
                st.slider("Valor de -l", 0, 500, 15, 1, key="fastp_l")
        with c4:
            st.number_input("Máx. Ns (-n)", min_value=0, max_value=10, value=0, step=1, key="fastp_n")
            st.number_input("Máx. % não-qual. (-u)", min_value=0, max_value=100, value=0, step=1, key="fastp_u")

        st.markdown("**Cortes dirigidos (cut_*)**")
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1: st.checkbox("--cut_front", value=False, key="fastp_cut_front")
        with cc2: st.checkbox("--cut_tail",  value=False, key="fastp_cut_tail")
        with cc3: st.number_input("cut_mean_quality", min_value=0, max_value=40, value=20, step=1, key="fastp_cut_meanq")
        with cc4: st.number_input("cut_window_size", min_value=1, max_value=100, value=4, step=1, key="fastp_cut_win")

        st.checkbox("polyG (-g)", value=False, key="fastp_poly_g")
        fastp_extra = st.text_input("Extra avançado (append)", value=st.session_state.get("fastp_extra",""), key="fastp_extra")

        parts = []
        if st.session_state.get("fastp_dash3", True): parts.append("-3")
        if st.session_state.get("fastp_enable_5prime"): parts.append("-5")
        parts += ["-M", str(st.session_state.get("fastp_M", 20))]
        parts += ["-W", str(st.session_state.get("fastp_W", 5))]
        if st.session_state.get("fastp_q_enable"): parts += ["-q", str(st.session_state.get("fastp_q", 20))]
        if st.session_state.get("fastp_l_enable"): parts += ["-l", str(st.session_state.get("fastp_l", 15))]
        n_val = st.session_state.get("fastp_n", 0);   u_val = st.session_state.get("fastp_u", 0)
        if n_val: parts += ["-n", str(n_val)]
        if u_val: parts += ["-u", str(u_val)]
        if st.session_state.get("fastp_cut_front"): parts.append("--cut_front")
        if st.session_state.get("fastp_cut_tail"):  parts.append("--cut_tail")
        if st.session_state.get("fastp_cut_front") or st.session_state.get("fastp_cut_tail"):
            parts += ["--cut_mean_quality", str(st.session_state.get("fastp_cut_meanq", 20))]
            parts += ["--cut_window_size",  str(st.session_state.get("fastp_cut_win", 4))]
        if st.session_state.get("fastp_detect_adapter_pe"): parts.append("--detect_adapter_for_pe")
        if st.session_state.get("fastp_poly_g"): parts.append("-g")
        if (st.session_state.get("fastp_extra") or "").strip():
            parts.append(st.session_state["fastp_extra"].strip())

        fastp_opts_value = " ".join(parts)
        st.caption(f"**fastp_opts:** `{fastp_opts_value}`")
    else:
        fastp_opts_value = st.text_input(
            "Linha completa do fastp (avançado)",
            value=st.session_state.get("fastp_opts_text","-3 -M 20 -W 5"),
            key="fastp_opts_text",
        )

# ------------------------- Unicycler -------------------------
with st.expander("Parâmetros do Unicycler", expanded=False):
    st.radio("Modo", ["conservative","normal","bold"], index=1, key="unicycler_mode")
    st.number_input("min_fasta_length", 0, 100000, 1000, 100, key="unicycler_min_len")
    st.text_input("Extra (append)", value=st.session_state.get("unicycler_extra",""), key="unicycler_extra")
    uni_parts = ["--mode", st.session_state.get("unicycler_mode","normal")]
    if st.session_state.get("unicycler_min_len", 1000):
        uni_parts += ["--min_fasta_length", str(int(st.session_state["unicycler_min_len"]))]
    if (st.session_state.get("unicycler_extra") or "").strip():
        uni_parts.append(st.session_state["unicycler_extra"].strip())
    unicycler_opts_value = " ".join(uni_parts)
    st.caption(f"unicycler_opts: `{unicycler_opts_value}`")

# ------------------------- Extra Params + Relatórios -------------------------
extra_params_input = st.text_input("Parâmetros extras (linha crua)", value=st.session_state.get("extra_params",""), key="extra_params")
computed_extra = extra_params_input
if st.session_state.get("fofn_use") and fofn_out:
    computed_extra = (computed_extra + f" --samples {shlex.quote(fofn_out)}").strip()

with st.expander("Relatórios (Nextflow)", expanded=False):
    rep = st.checkbox("-with-report", value=True, key="with_report")
    tim = st.checkbox("-with-timeline", value=True, key="with_timeline")
    trc = st.checkbox("-with-trace", value=True, key="with_trace")

# ------------------------- Montagem do comando -------------------------
def build_bactopia_cmd(params: dict) -> str:
    profile = params.get("profile","docker")
    outdir = params.get("outdir", DEFAULT_OUTDIR)
    datasets = params.get("datasets")
    fastp_opts=params.get("fastp_opts"); unicycler_opts=params.get("unicycler_opts")
    extra=params.get("extra_params"); resume=params.get("resume", True)
    threads=params.get("threads"); memory=params.get("memory")
    with_report=params.get("with_report"); with_timeline=params.get("with_timeline"); with_trace=params.get("with_trace")

    base = ["nextflow","run","bactopia/bactopia","-profile",profile,"--outdir",outdir]
    if datasets: base += ["--datasets", datasets]

    # Relatórios (salvos no outdir)
    report_dir = pathlib.Path(outdir)
    if with_report:   base += ["-with-report", str(report_dir / "nf-report.html")]
    if with_timeline: base += ["-with-timeline", str(report_dir / "nf-timeline.html")]
    if with_trace:    base += ["-with-trace", str(report_dir / "nf-trace.txt")]

    if fastp_opts:     base += ["--fastp_opts", fastp_opts]
    if unicycler_opts: base += ["--unicycler_opts", unicycler_opts]

    # Mantidos apenas estes recursos globais:
    if threads:        base += ["--max_cpus", str(threads)]
    if memory:         base += ["--max_memory", memory]
    if resume:         base += ["-resume"]

    if extra:          base += shlex.split(extra)

    return " ".join(shlex.quote(x) for x in base)

params = {
    "profile": st.session_state.get("profile"),
    "outdir": st.session_state.get("outdir"),
    "datasets": st.session_state.get("datasets") or None,
    "fastp_opts": (fastp_opts_value.strip() if 'fastp_opts_value' in locals() and fastp_opts_value.strip() else None),
    "unicycler_opts": (unicycler_opts_value.strip() if 'unicycler_opts_value' in locals() and unicycler_opts_value.strip() else None),
    "extra_params": computed_extra or None,
    "resume": st.session_state.get("resume", True),
    "threads": st.session_state.get("threads") or None,
    "memory": (f"{st.session_state.get('memory_gb')} GB" if st.session_state.get('memory_gb') else None),
    "with_report": st.session_state.get("with_report", True),
    "with_timeline": st.session_state.get("with_timeline", True),
    "with_trace": st.session_state.get("with_trace", True),
}
cmd = build_bactopia_cmd(params)

st.caption(f"Profile: {params['profile']} | Outdir: {params['outdir']}")
st.code(cmd, language="bash")

# ------------------------- Validação pré-execução -------------------------
def preflight_validate(params: dict) -> list[str]:
    errs = []
    prof = params.get("profile")
    if prof == "docker" and not docker_available():
        errs.append("Profile 'docker' selecionado, mas Docker não está disponível no PATH.")
    if prof == "singularity" and not singularity_available():
        errs.append("Profile 'singularity' selecionado, mas Singularity/Apptainer não está disponível no PATH.")

    def _must_exist(pth, label):
        if pth and not pathlib.Path(pth).exists():
            errs.append(f"Caminho não existe: {label} = {pth}")
    _must_exist(params.get("outdir"), "outdir")
    _must_exist(params.get("datasets"), "datasets")
    _must_exist(fofn_out, "FOFN (samples.txt)")

    return errs

_errors = preflight_validate(params)
if _errors:
    st.error("Erros de configuração encontrados. Corrija antes de executar:")
    for e in _errors: st.markdown(f"- {e}")

# ------------------------- Botões Execução / Clean -------------------------
col1, col2, col3 = st.columns([1,1,2])
with col1:
    start_main = st.button("▶️ Executar (async)", key="btn_main_start", disabled=st.session_state.get("main_running", False))
with col2:
    stop_main = st.button("⏹️ Interromper", key="btn_main_stop", disabled=not st.session_state.get("main_running", False))
with col3:
    c1, c2, c3 = st.columns([1,1,2])
    with c1: st.checkbox("Confirmar", value=False, key="confirm_clean")
    with c2: st.checkbox("Manter logs (-k)", value=False, key="clean_keep_logs")
    with c3: st.checkbox("Todas execuções", value=False, key="clean_all_runs")
    clean_clicked = st.button("🧹 Limpar ambiente", key="btn_clean_main", disabled=not st.session_state.get("confirm_clean", False))

status_box_main = st.empty()
report_zone_main = st.empty()
log_container_main = st.empty()

# --- LIMPEZA DE EXECUÇÕES ---
if clean_clicked:
    if st.session_state.get("main_running", False):
        request_stop_ns("main")
        time.sleep(0.8)

    launch_dir = pathlib.Path.cwd()

    if not nextflow_available():
        st.error("Nextflow não encontrado no PATH.")
    else:
        all_runs  = st.session_state.get("clean_all_runs", False)
        keep_logs = st.session_state.get("clean_keep_logs", False)

        try:
            log_res = subprocess.run(
                ["nextflow", "log", "-q"],
                cwd=str(launch_dir), text=True, capture_output=True, check=False
            )
            raw_names = [ln.strip() for ln in (log_res.stdout or "").splitlines() if ln.strip()]
            seen = set(); run_names = []
            for rn in raw_names:
                if rn not in seen:
                    seen.add(rn); run_names.append(rn)

            if not run_names:
                st.info("Nenhuma execução encontrada pelo 'nextflow log'.")
            else:
                targets = [run_names[-1]] if not all_runs else list(reversed(run_names))
                failures = []; cleaned  = 0
                for rn in targets:
                    cmdc = ["nextflow", "clean", "-f"] + (["-k"] if keep_logs else []) + [rn]
                    st.code(" ".join(shlex.quote(x) for x in cmdc), language="bash")
                    res = subprocess.run(cmdc, cwd=str(launch_dir), text=True, capture_output=True, check=False)
                    if res.returncode == 0:
                        cleaned += 1
                    else:
                        msg = (res.stderr or res.stdout or "").strip()
                        failures.append((rn, msg))

                if cleaned and not failures:
                    if all_runs:
                        st.success(f"Limpeza realizada para {cleaned} execução(ões).")
                    else:
                        st.success(f"Limpeza realizada para: {targets[0]}")
                elif cleaned and failures:
                    st.warning(f"Limpeza parcial: {cleaned} ok, {len(failures)} com erro.")
                else:
                    st.error("Falha ao limpar." if not all_runs else "Falha ao limpar todas as execuções.")

                for rn, msg in failures:
                    st.markdown(f"- **{rn}**")
                    if msg:
                        st.code(msg)

                if any("Missing cache index file" in (m or "") for _, m in failures):
                    st.warning(
                        "Algumas execuções não possuem índice de cache (`.nextflow/cache`). "
                        "Nesses casos o `nextflow clean` não consegue mapear o `work/`. "
                        "Se necessário, faça uma limpeza manual/forçada de `work/` e `.nextflow/cache/` (irreversível)."
                    )
        except Exception as e:
            st.exception(e)

if stop_main:
    request_stop_ns("main"); status_box_main.warning("Solicitada interrupção…")

if start_main:
    if _errors:
        st.error("Execução bloqueada pelas validações acima.")
    elif not nextflow_available():
        st.error("Nextflow não encontrado no PATH.")
    else:
        try:
            stdbuf = shutil.which("stdbuf")
            full_cmd = f"stdbuf -oL -eL {cmd}" if stdbuf else cmd
            status_box_main.info("Executando (async).")
            start_async_runner_ns(full_cmd, "main")
        except Exception as e:
            st.error(f"Falha ao iniciar (async): {e}")

if st.session_state.get("main_running", False):
    drain_log_queue_ns("main", tail_limit=200, max_pull=500)
    render_log_box_ns("main")
    finished = check_status_and_finalize_ns(params.get("outdir", DEFAULT_OUTDIR), "main", status_box_main, report_zone_main)
    if not finished:
        time.sleep(0.3); _st_rerun()
else:
    render_log_box_ns("main")
