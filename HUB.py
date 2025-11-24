# HUB.py — Hub multipáginas
# ---------------------------------------------------------------------
# Requer: streamlit>=1.30, Nextflow (+ Docker/Apptainer) instalados no PATH.
# ---------------------------------------------------------------------

import os
import pathlib
import shutil
import platform
import streamlit as st

# ============================= Config geral =============================
st.set_page_config(page_title="BEAR-HUB", page_icon="🐻", layout="wide")

APP_ROOT = pathlib.Path.cwd()
PAGES_DIR = APP_ROOT / "pages"
PAGE_BACTOPIA = PAGES_DIR / "BACTOPIA.py"
PAGE_TOOLS = PAGES_DIR / "BACTOPIA-TOOLS.py"
PAGE_PORT = PAGES_DIR / "PORT.py"
PAGE_TEST = PAGES_DIR / "TEST.py"

# ============================= Utils =============================
def which(cmd: str):
    from shutil import which as _which
    return _which(cmd)

def env_badge(label: str, ok: bool) -> str:
    return f"{'✅' if ok else '❌'} {label}"

def ensure_pages_hint():
    missing = []
    if not PAGE_BACTOPIA.exists():
        # Se o arquivo estiver na raiz do projeto, sugira mover
        if (APP_ROOT / "BACTOPIA.py").exists():
            missing.append("`pages/BACTOPIA.py` (encontrado `./BACTOPIA.py`; mova para `pages/`)")
        else:
            missing.append("`pages/BACTOPIA.py`")
    if not PAGE_TOOLS.exists():
        if (APP_ROOT / "BACTOPIA-TOOLS.py").exists():
            missing.append("`pages/app_tBACTOPIA-TOOLSools.py` (encontrado `./BACTOPIA-TOOLS.py`; mova para `pages/`)")
        else:
            missing.append("`pages/BACTOPIA-TOOLS.py`")
    if not PAGE_PORT.exists():
        if (APP_ROOT / "").exists():
            missing.append("`pages/PORT.py` (encontrado `./PORT.py`; mova para `pages/`)")
        else:
            missing.append("`pages/PORT.py`")
    return missing

# ============================= Header =============================
st.title("🧬 BEAR-Hub 🐻")
st.caption("Central com navegação para as duas páginas: **Main (FOFN/pipeline)** e **Ferramentas oficiais (--wf)**.")

# Ambiente (diagnóstico rápido)
nf_ok = which("nextflow") is not None
docker_ok = which("docker") is not None
sing_ok = which("singularity") is not None or which("apptainer") is not None

with st.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SO", platform.system())
    c2.write(env_badge("Nextflow", nf_ok))
    c3.write(env_badge("Docker", docker_ok))
    c4.write(env_badge("Singularity/Apptainer", sing_ok))
st.divider()

# ============================= Checagem de páginas =============================
missing = ensure_pages_hint()
if missing:
    st.error("Páginas não encontradas:")
    for m in missing:
        st.markdown(f"- {m}")
    st.info(
        "Crie a pasta `pages/` na raiz do projeto e mova os arquivos para lá.\n\n"
        "Exemplo:\n"
        "`mkdir -p pages && mv BACTOPIA.py pages/BACTOPIA.py && mv BACTOPIA-TOOLS.py pages/BACTOPIA-TOOLS.py`"
    )
else:
    # Navegação por cartões + links nativos do Streamlit
    st.subheader("Navegar")
    cA, cB = st.columns(2)

    with cA:
        st.markdown("### 🦠 Bactopia — Pipeline Principal")
        st.caption("Gera **FOFN** automaticamente, monta o comando do **Bactopia** e executa via Nextflow (assíncrono).")
        st.page_link("pages/BACTOPIA.py", label="Abrir Bactopia", icon="🧪")

    with cB:
        st.markdown("### 🧰 Ferramentas Bactopia")
        st.caption("Executa **amrfinderplus, rgi, abricate, mobsuite, mlst, pangenome, mashtree** nas amostras concluídas.")
        st.page_link("pages/BACTOPIA-TOOLS.py", label="Abrir página Ferramentas", icon="🧰")



    cA1, cB2 = st.columns(2)

    with cA1:
        st.markdown("### 🍷 PORT — Plasmid Outbreak Investigation Tool")
        st.caption("PORT.")
        st.page_link("pages/BACTOPIA.py", label="Abrir PORT", icon="🍷")



    st.divider()
    with st.expander("Dicas rápidas", expanded=False):
        st.markdown(
            "- Cada página tem suas próprias opções e logs.\n"
            "- Se faltar `Nextflow` no PATH, instale e reabra o terminal/sessão."
        )

# Rodapé
st.markdown(
    "<hr style='opacity:0.3'/>"
    "<small>BEAR-HUB — multipage hub. "
    "",
    unsafe_allow_html=True
)
