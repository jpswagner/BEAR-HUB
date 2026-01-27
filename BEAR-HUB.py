# BEAR-HUB.py — Multi-page Hub
# ---------------------------------------------------------------------
# Requires: streamlit>=1.30, Nextflow (+ Docker/Apptainer) installed in PATH.
# ---------------------------------------------------------------------

"""
BEAR-HUB Main Application.

This module serves as the entry point for the BEAR-HUB Streamlit application.
It acts as a central hub (Dashboard) providing navigation to different
modules of the application:
    - Bactopia (Main Pipeline)
    - Bactopia Tools (Post-processing)
    - Merlin (Species-specific workflows)
    - PORT (Plasmid Outbreak Investigation Tool)

The script checks for the existence of required page files and environment
dependencies (Nextflow, Docker) and renders the main landing page.
"""

import pathlib
import streamlit as st
import utils  # Import the new utility module

# ============================= General config =============================
st.set_page_config(page_title="BEAR-HUB", page_icon="🐻", layout="wide")

APP_ROOT = pathlib.Path(__file__).resolve().parent
PAGES_DIR = APP_ROOT / "pages"
PAGE_BACTOPIA = PAGES_DIR / "BACTOPIA.py"
PAGE_TOOLS = PAGES_DIR / "BACTOPIA-TOOLS.py"
PAGE_MERLIN = PAGES_DIR / "MERLIN.py"
PAGE_PORT = PAGES_DIR / "PORT.py"

# Discover project root (folder that holds /static)
if (APP_ROOT / "static").is_dir():
    PROJECT_ROOT = APP_ROOT
elif (APP_ROOT.parent / "static").is_dir():
    PROJECT_ROOT = APP_ROOT.parent
else:
    PROJECT_ROOT = APP_ROOT  # fallback

# ============================= Utils =============================
# Using utils.which and utils.env_badge instead of defining them locally

def ensure_pages_hint():
    """
    Check that all required page files exist in the `pages/` directory.

    Scans for the expected page files (`BACTOPIA.py`, `BACTOPIA-TOOLS.py`,
    `MERLIN.py`, `PORT.py`) in the `pages/` subdirectory. If a file is missing
    but found in the project root, it suggests moving it.

    Returns:
        list[str]: A list of error messages describing missing pages or
        suggested actions. Returns an empty list if all pages are correctly placed.
    """
    missing = []
    # BACTOPIA
    if not PAGE_BACTOPIA.exists():
        if (APP_ROOT / "BACTOPIA.py").exists():
            missing.append(
                "`pages/BACTOPIA.py` (found `./BACTOPIA.py`; move it to `pages/`)"
            )
        else:
            missing.append("`pages/BACTOPIA.py`")

    # BACTOPIA-TOOLS
    if not PAGE_TOOLS.exists():
        if (APP_ROOT / "BACTOPIA-TOOLS.py").exists():
            missing.append(
                "`pages/BACTOPIA-TOOLS.py` (found `./BACTOPIA-TOOLS.py`; move it to `pages/`)"
            )
        else:
            missing.append("`pages/BACTOPIA-TOOLS.py`")

    # MERLIN
    if not PAGE_MERLIN.exists():
        if (APP_ROOT / "MERLIN.py").exists():
            missing.append(
                "`pages/MERLIN.py` (found `./MERLIN.py`; move it to `pages/`)"
            )
        else:
            missing.append("`pages/MERLIN.py`")

    # PORT
    if not PAGE_PORT.exists():
        if (APP_ROOT / "PORT.py").exists():
            missing.append(
                "`pages/PORT.py` (found `./PORT.py`; move it to `pages/`)"
            )
        else:
            missing.append("`pages/PORT.py`")

    return missing

# ============================= Header =============================
ICON_PATH_BEAR_HUB = PROJECT_ROOT / "static" / "bear-hub-logo-bg.png"

if ICON_PATH_BEAR_HUB.is_file():
    left_co, cent_co, last_co = st.columns(3)
    with cent_co:
        st.image(str(ICON_PATH_BEAR_HUB), width=1000)
else:
    st.title("🧬 BEAR-HUB 🐻")

st.divider()

# Quick environment diagnostics (kept commented, now in English)
# nf_ok = utils.which("nextflow") is not None
# docker_ok = utils.which("docker") is not None
# sing_ok = utils.which("singularity") is not None or utils.which("apptainer") is not None
#
# with st.container():
#     c1, c2, c3, c4 = st.columns(4)
#     c1.metric("OS", platform.system())
#     c2.write(utils.env_badge("Nextflow", nf_ok))
#     c3.write(utils.env_badge("Docker", docker_ok))
#     c4.write(utils.env_badge("Singularity/Apptainer", sing_ok))



# ============================= Page checks =============================
missing = ensure_pages_hint()
if missing:
    st.error("Required pages not found:")
    for m in missing:
        st.markdown(f"- {m}")
    st.info(
        "Create the `pages/` folder at the project root and move the files there.\n\n"
        "Example:\n"
        "`mkdir -p pages && mv BACTOPIA.py pages/BACTOPIA.py && mv BACTOPIA-TOOLS.py pages/BACTOPIA-TOOLS.py`"
    )
else:
    # Navigation cards + Streamlit native routing


    #st.markdown("## Hub")
    #st.divider()
    cA, cB = st.columns(2)

    with cA:
        st.markdown("### Bactopia — Main Pipeline")
        st.caption(
            "Automatically builds a **FOFN**, assembles the **Bactopia** command and runs it via Nextflow (async)."
        )
        if st.button("BACTOPIA", type="primary", icon="🦠", use_container_width=True):
            st.switch_page("pages/BACTOPIA.py")


    with cB:
        st.markdown("### Bactopia Tools")
        st.caption(
            "Runs **amrfinderplus, rgi, abricate, mobsuite, mlst, pangenome, mashtree** "
            "on completed samples."
        )
        if st.button("BACTOPIA TOOLS", type="primary", icon="🧰", use_container_width=True):
            st.switch_page("pages/BACTOPIA-TOOLS.py")
        

    cA1, cB2 = st.columns(2)

    with cA1:
        st.markdown("### Bactopia MERLIN")
        st.caption("Runs species-specific workflows on completed samples.")
        if st.button("BACTOPIA MERLIN", type="primary", icon="🧙🏻", use_container_width=True):
            st.switch_page("pages/MERLIN.py")

    with cB2:
        st.markdown("### PORT — Plasmid Outbreak Investigation Tool")
        st.caption("(IN DEVELOPMENT) Wrapper to run **PORT** for plasmid-focused outbreak investigations.")
        if st.button("PORT", type="secondary", icon="🍷", use_container_width=True):
            st.switch_page("pages/PORT.py")

    st.divider()
    with st.expander("Quick tips", expanded=False):
        st.markdown(
            "- Each page has its own options and logs.\n"
            "- If `Nextflow` is missing from your PATH, install it and restart your terminal/session.\n"
            "- Docker or Singularity/Apptainer must be installed if you intend to run container profiles."
        )

    st.divider()

    st.markdown("### System")
    cS, _ = st.columns([1, 3])
    with cS:
        if st.button("Updates & Status", icon="🔄", use_container_width=True):
            st.switch_page("pages/UPDATES.py")

# ============================= Footer (disclaimer) =============================
st.markdown(
    "<hr style='opacity:0.3'/>"
    "<small>"
    """
PT-BR

Este projeto fornece apenas uma interface (hub/UI) para orquestrar análises com o Bactopia (https://github.com/bactopia).
Bactopia é um software de terceiros, desenvolvido e mantido independentemente por seus autores originais.
Não temos qualquer vínculo oficial com o projeto Bactopia.

EN

This project only provides a user interface (hub/UI) to orchestrate analyses with Bactopia (https://github.com/bactopia).
Bactopia is third-party software, developed and maintained independently by its original authors.
We have no official affiliation with the Bactopia project.
    """,
    unsafe_allow_html=True,
)
