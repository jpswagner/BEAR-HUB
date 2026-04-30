# BEAR-HUB.py — Multi-page Hub
# ---------------------------------------------------------------------
# Requires: streamlit>=1.30, Nextflow (+ Docker/Apptainer) installed in PATH.
# ---------------------------------------------------------------------

"""
BEAR-HUB main application.

Entry point for the BEAR-HUB Streamlit app. Acts as a dashboard that
dispatches to the per-tool pages defined in `tools.yaml`.

Adding a new tool:
    1. Append an entry to tools.yaml.
    2. Drop a pages/<NAME>.py file that calls utils.init_page(...).
"""

import pathlib
import streamlit as st

import utils
from utils.history import get_runs

# Load env config early so BACTOPIA_ENV_PREFIX / NXF_CONDA_EXE are available
# to every imported sub-module for the duration of this Streamlit session.
utils.bootstrap_bear_env_from_file()

# ============================= General config =============================
st.set_page_config(page_title="BEAR-HUB", page_icon="🐻", layout="wide")

PROJECT_ROOT = utils.PROJECT_ROOT

# ============================= Header =============================
ICON_PATH_BEAR_HUB = PROJECT_ROOT / "static" / "bear-hub-logo-bg.png"

if ICON_PATH_BEAR_HUB.is_file():
    _, cent_co, _ = st.columns(3)
    with cent_co:
        st.image(str(ICON_PATH_BEAR_HUB), width=1000)
else:
    st.title("🧬 BEAR-HUB 🐻")

st.divider()

# ============================= Tool registry =============================

tools = utils.load_tools()
missing = [t for t in tools if not t.exists(PROJECT_ROOT)]

if not tools:
    st.error(
        "No tools found in `tools.yaml`. "
        "Make sure the file exists at the project root and lists at least one tool."
    )
elif missing:
    st.error("Some tools listed in `tools.yaml` point at missing page files:")
    for t in missing:
        st.markdown(f"- **{t.name}** → `{t.page}`")
    st.info("Create the missing page file(s), or remove the entry from `tools.yaml`.")
else:
    # Render tool cards in a 2-column grid. Extra tools wrap onto new rows.
    for i in range(0, len(tools), 2):
        cols = st.columns(2)
        for col, tool in zip(cols, tools[i:i + 2]):
            with col:
                heading = f"### {tool.icon} {tool.name}"
                if tool.status_badge:
                    heading = f"{heading}{tool.status_badge}"
                st.markdown(heading)
                if tool.tagline:
                    st.caption(f"*{tool.tagline}*")
                if tool.description:
                    st.caption(tool.description)
                if st.button(
                    tool.name.upper(),
                    key=f"go_{tool.id}",
                    type=tool.button_type,
                    icon=tool.icon,
                    width="stretch",
                ):
                    st.switch_page(tool.page)

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
        if st.button("Updates & Status", icon="🔄", width="stretch"):
            st.switch_page("pages/UPDATES.py")

    st.divider()
    with st.expander("Recent runs", expanded=False):
        runs = get_runs(limit=20)
        if not runs:
            st.caption("No runs recorded yet. Run a pipeline to see history here.")
        else:
            import pandas as pd
            df = pd.DataFrame(runs)[["started_at", "finished_at", "page", "samples", "status"]]
            df.columns = ["Started", "Finished", "Module", "Samples", "Status"]
            st.dataframe(df, width="stretch", hide_index=True)

# ============================= Footer =============================
# Disclaimer retained in English only; PT-BR version lives in README.md.
st.markdown(
    "<hr style='opacity:0.3'/>"
    "<small>"
    "This project only provides a user interface (hub/UI) to orchestrate analyses with "
    "<a href='https://github.com/bactopia'>Bactopia</a>. Bactopia is third-party software, "
    "developed and maintained independently by its original authors. We have no official "
    "affiliation with the Bactopia project."
    "</small>",
    unsafe_allow_html=True,
)
