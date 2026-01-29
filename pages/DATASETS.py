# DATASETS.py — Bactopia Datasets Manager
# ---------------------------------------------------------------------
# • UI to run `bactopia datasets` via Docker
# • Allows downloading/updating MLST, Ariba, and RefSeq datasets
# • Outputs to a local directory for use in BACTOPIA.py
# ---------------------------------------------------------------------

import os
import sys
import shlex
import time
import pathlib
import streamlit as st

# Import utility module from parent directory
try:
    import utils
except ImportError:
    sys.path.append(str(pathlib.Path(__file__).parent.parent))
    import utils

# ============================= Configuration =============================
st.set_page_config(
    page_title="Bactopia Datasets | BEAR-HUB",
    page_icon="💽",
    layout="wide",
)

utils.bootstrap_bear_env_from_file()

APP_ROOT = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent if (APP_ROOT.parent / "static").is_dir() else APP_ROOT

# ============================= Sidebar =============================
with st.sidebar:
    st.header("Environment")
    docker_ok = utils.docker_available()
    st.write(f"Docker: {'✅' if docker_ok else '❌'}")
    if not docker_ok:
        st.error("Docker is required to run `bactopia datasets`.")

    st.info(
        "**Note:** This tool runs `bactopia datasets` inside a container "
        "to download reference data to your host machine."
    )

# ============================= Header =============================
st.title("💽 Bactopia Datasets")
st.markdown(
    """
    Use this tool to download or update reference datasets (MLST, Ariba, Minmer, Prokka).

    1. Select a **local folder** (e.g. `~/BEAR_DATA/datasets/kpneumoniae`).
    2. Enter the **Species** (e.g. `Klebsiella pneumoniae`).
    3. Click **Run** to download the latest schemes from PubMLST and other sources.
    4. Once finished, use this folder in the **BACTOPIA** page (Global parameters > `datasets`).
    """
)

# ============================= Main Form =============================

with st.expander("Configuration", expanded=True):
    c1, c2 = st.columns([1, 1])
    with c1:
        # Default image from user logs or latest known stable
        default_image = "quay.io/bactopia/bactopia:3.2.0"
        image = st.text_input(
            "Docker Image",
            value=default_image,
            key="ds_image",
            help="The Bactopia container image to use."
        )
    with c2:
        # Default output base
        default_base = os.getenv("BEAR_HUB_DATA", str(pathlib.Path.home() / "BEAR_DATA" / "datasets"))
        outdir = utils.path_picker(
            "Output Directory (Host)",
            key="ds_outdir",
            mode="dir",
            start=default_base,
            help="The folder where datasets will be downloaded. It is recommended to use a separate folder per species."
        )

    st.divider()

    c3, c4 = st.columns([1, 1])
    with c3:
        species = st.text_input(
            "Species",
            value="Klebsiella pneumoniae",
            key="ds_species",
            help="Scientific name of the species (must be in quotes if using CLI, but here just type it)."
        )
        limit = st.number_input(
            "Limit (RefSeq genomes)",
            min_value=0,
            value=100,
            step=10,
            key="ds_limit",
            help="Number of RefSeq genomes to download for validation (0 to skip downloading genomes, if supported)."
        )

    with c4:
        st.checkbox("--include_genus", value=True, key="ds_include_genus", help="Include all species in the genus for Minmer/Prokka.")
        st.caption("**Optimization (skip components):**")
        skip_ariba = st.checkbox("--skip_ariba", value=False, key="ds_skip_ariba")
        skip_minmer = st.checkbox("--skip_minmer", value=False, key="ds_skip_minmer")
        skip_prokka = st.checkbox("--skip_prokka", value=False, key="ds_skip_prokka")
        # MLST is usually what we want, so no skip option for it here (though bactopia has one)

    st.divider()

    c5, c6 = st.columns([1, 1])
    with c5:
         run_as_user = st.checkbox(
             "Run as current user (fix permissions)",
             value=True,
             key="ds_run_as_user",
             help="Runs the container with `-u $(id -u):$(id -g)` so files are owned by you."
         )
    with c6:
        extra_args = st.text_input("Extra arguments", key="ds_extra", help="Additional flags to pass to `bactopia datasets`.")


# ============================= Command Logic =============================

def build_datasets_cmd(
    image: str,
    host_outdir: str,
    species: str,
    include_genus: bool,
    limit: int,
    skips: dict,
    run_as_user: bool,
    extra: str
) -> str:
    """Build the docker run command for bactopia datasets."""

    # Resolve host path
    host_path = pathlib.Path(host_outdir).expanduser().resolve()

    # Internal mount point
    mount_point = "/data"

    # Base docker command
    cmd = ["docker", "run", "--rm"]

    # Volume mount
    cmd += ["-v", f"{host_path}:{mount_point}"]

    # Working dir
    cmd += ["-w", mount_point]

    # User permissions
    if run_as_user:
        # Get UID/GID
        uid = os.getuid()
        gid = os.getgid()
        cmd += ["-u", f"{uid}:{gid}"]
        # Set HOME to /data to avoid permission issues with /root or /home/bactopia
        cmd += ["-e", f"HOME={mount_point}"]

    cmd.append(image)

    # Bactopia tool command
    cmd += ["bactopia", "datasets"]

    # Params
    cmd += ["--species", species]
    cmd += ["--outdir", mount_point]
    cmd += ["--limit", str(limit)]

    if include_genus:
        cmd.append("--include_genus")

    if skips.get("ariba"): cmd.append("--skip_ariba")
    if skips.get("minmer"): cmd.append("--skip_minmer")
    if skips.get("prokka"): cmd.append("--skip_prokka")

    if extra:
        cmd += shlex.split(extra)

    return " ".join(shlex.quote(x) for x in cmd)

# ============================= Execution =============================

# Calculate command for display/run
skips = {
    "ariba": st.session_state.get("ds_skip_ariba"),
    "minmer": st.session_state.get("ds_skip_minmer"),
    "prokka": st.session_state.get("ds_skip_prokka"),
}

if outdir and species:
    full_cmd = build_datasets_cmd(
        image=image,
        host_outdir=outdir,
        species=species,
        include_genus=st.session_state.get("ds_include_genus", True),
        limit=st.session_state.get("ds_limit", 100),
        skips=skips,
        run_as_user=st.session_state.get("ds_run_as_user", True),
        extra=st.session_state.get("ds_extra", "")
    )
    st.code(full_cmd, language="bash")
else:
    full_cmd = ""
    if not outdir:
        st.warning("Please select an output directory.")

# Action Buttons
c_run, c_stop = st.columns([1, 4])
with c_run:
    start_btn = st.button(
        "▶️ Run",
        key="btn_ds_start",
        disabled=st.session_state.get("ds_running", False) or not full_cmd
    )
with c_stop:
    stop_btn = st.button(
        "⏹️ Stop",
        key="btn_ds_stop",
        disabled=not st.session_state.get("ds_running", False)
    )

status_box = st.empty()

if stop_btn:
    utils.request_stop_ns("ds")
    status_box.warning("Stop requested...")

if start_btn:
    if not utils.docker_available():
        st.error("Docker is not available.")
    else:
        status_box.info("Running `bactopia datasets` (async)...")
        utils.start_async_runner_ns(full_cmd, "ds")

# Log Viewer
if st.session_state.get("ds_running", False):
    utils.drain_log_queue_ns("ds", tail_limit=500)
    utils.render_log_box_ns("ds", height=500)
    finished = utils.check_status_and_finalize_ns("ds", status_box)
    if not finished:
        time.sleep(0.5)
        utils._st_rerun()
else:
    utils.render_log_box_ns("ds", height=500)
