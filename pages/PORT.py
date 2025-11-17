# PORT.py — Página Streamlit para rodar o pipeline PORT via Nextflow
# Coloque este arquivo, por exemplo, em `pages/PORT.py` dentro do seu app.

import os
import shlex
import time
import pathlib
import subprocess
import shutil
import threading
from queue import Queue, Empty

import streamlit as st


# ========================= Helpers de estado =========================

def _init_state():
    if "port_log_queue" not in st.session_state:
        st.session_state["port_log_queue"] = Queue()
    if "port_log_text" not in st.session_state:
        st.session_state["port_log_text"] = ""
    if "port_running" not in st.session_state:
        st.session_state["port_running"] = False
    if "port_status" not in st.session_state:
        st.session_state["port_status"] = "Aguardando configuração."
    if "port_proc" not in st.session_state:
        st.session_state["port_proc"] = None
    if "port_thread" not in st.session_state:
        st.session_state["port_thread"] = None
    if "port_assemblies_dir" not in st.session_state:
        st.session_state["port_assemblies_dir"] = ""


def _st_rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()


def nextflow_available() -> bool:
    return shutil.which("nextflow") is not None


# ========================= Log / execução async =========================

def drain_port_logs() -> str:
    """
    Puxa tudo que está na fila de logs e concatena em uma string única.
    """
    log_q: Queue = st.session_state["port_log_queue"]
    text = st.session_state.get("port_log_text", "")
    while True:
        try:
            line = log_q.get_nowait()
        except Empty:
            break
        else:
            text += line + "\n"
    st.session_state["port_log_text"] = text
    return text


def launch_nextflow_async(cmd: str):
    """
    Lança o comando Nextflow em uma thread separada e joga stdout/stderr na fila de log.
    """
    if st.session_state.get("port_running", False):
        st.warning("Já existe uma execução do PORT em andamento.")
        return

    log_q: Queue = st.session_state["port_log_queue"]

    def runner():
        try:
            st.session_state["port_running"] = True
            st.session_state["port_status"] = "Executando PORT..."
            stdbuf = shutil.which("stdbuf")
            full_cmd = f"stdbuf -oL -eL {cmd}" if stdbuf else cmd

            proc = subprocess.Popen(
                full_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            st.session_state["port_proc"] = proc

            log_q.put(f"[PORT] Comando iniciado:\n{full_cmd}\n")

            for line in proc.stdout:
                log_q.put(line.rstrip())

            rc = proc.wait()
            log_q.put(f"[PORT] Execução finalizada com código de saída {rc}.")
        except Exception as e:
            log_q.put(f"[PORT] Erro durante a execução: {e}")
        finally:
            st.session_state["port_running"] = False
            st.session_state["port_status"] = "Execução finalizada."
            st.session_state["port_proc"] = None

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    st.session_state["port_thread"] = t


def stop_nextflow():
    """
    Envia um terminate para o processo do Nextflow.
    """
    proc = st.session_state.get("port_proc")
    if proc is not None and proc.poll() is None:
        proc.terminate()
        st.session_state["port_log_queue"].put("[PORT] Sinal de parada enviado (terminate).")
        st.session_state["port_status"] = "Parada solicitada..."
    else:
        st.info("Nenhuma execução ativa do PORT para parar.")


# ========================= Bactopia → assemblies =========================

def build_port_assemblies_from_bactopia(bactopia_run_dir: str) -> tuple[pathlib.Path, int]:
    """
    A partir de um diretório de saída do Bactopia, cria uma pasta 'port_assemblies'
    com symlinks para todos os FASTA encontrados (recursivamente).

    Retorna (caminho_da_pasta, número_de_links_criados).
    """
    run_path = pathlib.Path(bactopia_run_dir).expanduser().resolve()
    target = run_path / "port_assemblies"
    target.mkdir(parents=True, exist_ok=True)

    patterns = ("*.fa", "*.fna", "*.fasta")
    created = 0

    for pattern in patterns:
        for f in run_path.rglob(pattern):
            # Evita recursão dentro da própria pasta port_assemblies
            if "port_assemblies" in f.parts:
                continue

            # Nome base do sample (bem simples, só pra ter algo legível)
            sample_name = f.stem
            link_path = target / f"{sample_name}{f.suffix}"

            if link_path.exists():
                continue

            try:
                os.symlink(f, link_path)
                created += 1
            except FileExistsError:
                pass
            except OSError as e:
                # Se symlink falhar por qualquer motivo, apenas loga
                st.session_state["port_log_queue"].put(
                    f"[PORT] Não foi possível criar symlink para {f}: {e}"
                )

    return target, created


# ========================= UI principal =========================

def main():
    _init_state()

    st.title("PORT — Montagem Nanopore & Tipagem de Plasmídeos")

    st.markdown(
        """
Esta página permite rodar o pipeline **PORT** via Nextflow:

- **FASTQs próprios (Nanopore)** → `--input_dir`
- **Assemblies / saída do Bactopia** → `--assemblies` (com opção de montar uma pasta de assemblies a partir de um run do Bactopia)
"""
    )

    cols_top = st.columns([2, 1])
    with cols_top[0]:
        st.subheader("Configuração do PORT")

        # Caminho para o main.nf do PORT
        default_main_nf = "PORT/main.nf"
        main_nf_path = st.text_input(
            "Caminho para o main.nf do PORT",
            value=default_main_nf,
            help="Ex.: PORT/main.nf ou caminho absoluto até o main.nf",
        ).strip()

        if not main_nf_path:
            main_nf_path = "main.nf"

        # Profile de execução
        profile = st.selectbox(
            "Perfil de execução do Nextflow",
            options=["padrão (Docker)", "conda"],
            index=0,
            help="Se você não sabe, deixe em 'padrão (Docker)'. Para usar env Conda, escolha 'conda'.",
        )

        conda_env = ""
        if profile == "conda":
            conda_env = st.text_input(
                "Nome do ambiente Conda (opcional)",
                value="",
                help="Se já tiver um ambiente Conda pronto, informe o nome aqui para usar com --conda_env.",
            ).strip()

        # Tipo de entrada
        input_mode = st.radio(
            "Tipo de entrada",
            options=[
                "FASTQs Nanopore (reads próprios)",
                "Assemblies / saída do Bactopia (FASTA)",
            ],
            index=0,
        )

        input_dir = ""
        assemblies_dir = ""

        if input_mode.startswith("FASTQ"):
            input_dir = st.text_input(
                "Diretório com FASTQs (Nanopore)",
                value="input",
                help="Diretório que será passado para --input_dir (todos os FASTQ/FASTQ.GZ).",
            ).strip()
        else:
            assemblies_dir = st.text_input(
                "Diretório de assemblies (FASTA) para o PORT",
                value=st.session_state.get("port_assemblies_dir", ""),
                help="Diretório que será passado para --assemblies (contendo arquivos .fa/.fna/.fasta).",
            ).strip()

            with st.expander("Montar pasta de assemblies a partir de uma saída do Bactopia"):
                bactopia_run_dir = st.text_input(
                    "Diretório da execução do Bactopia",
                    value=str((pathlib.Path.cwd() / "bactopia_out").resolve()),
                    help="Pasta raiz de um run do Bactopia (o script irá procurar FASTA recursivamente).",
                ).strip()

                if st.button("Criar/atualizar pasta 'port_assemblies'"):
                    if not pathlib.Path(bactopia_run_dir).exists():
                        st.error("Diretório de saída do Bactopia não encontrado.")
                    else:
                        target, created = build_port_assemblies_from_bactopia(bactopia_run_dir)
                        st.session_state["port_assemblies_dir"] = str(target)
                        assemblies_dir = str(target)
                        st.success(
                            f"Criada/atualizada pasta de assemblies: {target}\n"
                            f"Symlinks criados para {created} arquivos FASTA."
                        )

        # Diretório de saída do PORT
        default_outdir = str((pathlib.Path.cwd() / "port_out").resolve())
        output_dir = st.text_input(
            "Diretório de saída do PORT",
            value=default_outdir,
            help="Diretório que será passado para --output_dir.",
        ).strip()

        # Parâmetros de montagem
        st.markdown("### Parâmetros de montagem")

        assembler = st.selectbox(
            "Assembler",
            options=["autocycler", "dragonflye"],
            index=0,
            help="Conforme documentação do PORT: autocycler ou dragonflye.",
        )

        read_type = st.text_input(
            "Read type (--read_type)",
            value="ont_r10",
            help="Ex.: ont_r9, ont_r10. Usado principalmente em pipelines com Medaka.",
        ).strip()

        medaka_model = st.text_input(
            "Medaka model (--medaka_model)",
            value="r1041_e82_400bps_sup",
            help="Modelo do Medaka para polimento (especialmente relevante para dragonflye).",
        ).strip()

        st.markdown("### Recursos globais (Nextflow)")

        col_res1, col_res2 = st.columns(2)
        with col_res1:
            max_cpus = st.number_input(
                "--max_cpus (opcional)",
                min_value=1,
                max_value=256,
                value=16,
                step=1,
                help="Limite global de CPUs para o Nextflow (deixe como está se não tiver certeza).",
            )
        with col_res2:
            max_memory = st.text_input(
                "--max_memory (opcional)",
                value="64.GB",
                help="Memória global para o Nextflow, ex.: 64.GB, 128.GB",
            ).strip()

        # Monta o comando (pré-visualização)
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

        if profile == "conda":
            cmd_parts += ["-profile", "conda"]
            if conda_env:
                cmd_parts += ["--conda_env", conda_env]

        if max_cpus:
            cmd_parts += ["--max_cpus", str(max_cpus)]
        if max_memory:
            cmd_parts += ["--max_memory", max_memory]

        # Sempre com -resume para permitir retomada
        cmd_parts.append("-resume")

        cmd_preview = " ".join(shlex.quote(p) for p in cmd_parts)

        st.markdown("#### Comando Nextflow (pré-visualização)")
        st.code(cmd_preview, language="bash")

    with cols_top[1]:
        st.subheader("Status / Controle")

        status_text = st.session_state.get("port_status", "Aguardando.")
        if st.session_state.get("port_running", False):
            st.info(status_text)
        else:
            st.success(status_text)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            start_clicked = st.button(
                "▶ Iniciar PORT",
                disabled=st.session_state.get("port_running", False),
            )
        with col_btn2:
            stop_clicked = st.button(
                "⏹ Parar",
                disabled=not st.session_state.get("port_running", False),
            )

        if start_clicked:
            # Validações básicas
            if not nextflow_available():
                st.error("Nextflow não encontrado no PATH. Verifique a instalação.")
            elif input_mode.startswith("FASTQ") and not input_dir:
                st.error("Informe o diretório com FASTQs para --input_dir.")
            elif (not input_mode.startswith("FASTQ")) and not assemblies_dir:
                st.error("Informe o diretório de assemblies para --assemblies.")
            else:
                launch_nextflow_async(cmd_preview)

        if stop_clicked:
            stop_nextflow()

    st.markdown("---")
    st.subheader("Logs do Nextflow (PORT)")

    log_text = drain_port_logs()
    st.text_area(
        "Saída da execução",
        value=log_text,
        height=400,
        help="Stdout/stderr do Nextflow (PORT).",
    )

    # Auto-refresh simples enquanto a execução estiver rodando
    if st.session_state.get("port_running", False):
        time.sleep(1.0)
        _st_rerun()


if __name__ == "__main__":
    main()
