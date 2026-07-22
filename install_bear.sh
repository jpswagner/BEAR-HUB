#!/usr/bin/env bash
# install_bear.sh — BEAR-HUB installer
# ---------------------------------------------------------------------------
# Sets up two conda environments (bear-hub, bactopia) and writes configuration
# to ~/.bear-hub/config.env so the app can find its dependencies at runtime.
#
# Usage:
#   bash install_bear.sh [--bactopia-version X.Y.Z]
#
# Environment overrides:
#   BACTOPIA_VERSION   Override the pinned Bactopia version (default: 4.0.0)
# ---------------------------------------------------------------------------
set -euo pipefail

# ── Versioned defaults ────────────────────────────────────────────────────────
# 4.0.0 is the validated version (requires Nextflow >= 26.04). Keep the conda
# package and this pin in sync — the app runs `-r v${BACTOPIA_VERSION}`.
BACTOPIA_VERSION="${BACTOPIA_VERSION:-4.0.0}"
# Reflex is pinned exactly (it makes breaking changes across patch releases).
REFLEX_VERSION="${REFLEX_VERSION:-0.9.3}"

# ── Directories ───────────────────────────────────────────────────────────────
# Derive the repo root from this script's own location so the installer works no
# matter where BEAR-HUB was cloned (any path, any user). An explicit
# BEAR_HUB_ROOT env var still wins, for non-standard layouts.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAR_HUB_ROOT="${BEAR_HUB_ROOT:-${SCRIPT_DIR}}"
DATA_DIR="${BEAR_HUB_ROOT}/data"
OUT_DIR="${BEAR_HUB_ROOT}/bactopia_out"
# New config location (read by utils/system.py → bootstrap_bear_env_from_file)
CONFIG_DIR="${HOME}/.bear-hub"
CONFIG_FILE="${CONFIG_DIR}/config.env"

# Conda env prefixes (local to the project tree)
ENVS_DIR="${BEAR_HUB_ROOT}/envs"
BEAR_PREFIX="${ENVS_DIR}/bear-hub"
BACTOPIA_PREFIX="${ENVS_DIR}/bactopia"

# Conda/mamba binaries (populated by check_prerequisites)
MAMBA_BIN=""
CONDA_BIN=""

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bactopia-version)
            BACTOPIA_VERSION="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Step 1: check_prerequisites — Docker + conda/mamba
# =============================================================================
check_prerequisites() {
    echo
    echo "=== Step 1: Checking prerequisites ==="

    # Docker
    if ! command -v docker >/dev/null 2>&1; then
        cat <<'EOF'

ERROR: 'docker' was not found in PATH.
BEAR-HUB runs Bactopia exclusively with '-profile docker', so Docker is mandatory.

Quick install for Ubuntu/Debian (as root or via sudo):

  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  # (Optional) add your user to the docker group:
  sudo usermod -aG docker "$USER"
  # Then log out and back in.

For other platforms: https://docs.docker.com/engine/install/
EOF
        exit 1
    fi
    echo "Docker found: $(command -v docker)"

    # CLI present != daemon running / user in the docker group. Warn (don't abort)
    # so the user can start the daemon later; runs need it though.
    if docker info >/dev/null 2>&1; then
        echo "Docker daemon: reachable."
    else
        echo
        echo "WARNING: 'docker' is installed but the daemon is not reachable."
        echo "  Bactopia runs ('-profile docker') will fail until this is fixed:"
        echo "    - start the daemon:   sudo systemctl start docker"
        echo "    - add your user:      sudo usermod -aG docker \"\$USER\"   (then log out/in)"
        echo "  Continuing installation..."
    fi

    # conda / mamba — detect (PATH or a common prefix), else auto-install Miniforge.
    detect_conda
    if [[ -z "${MAMBA_BIN}" && -z "${CONDA_BIN}" ]]; then
        if [[ "${BEAR_HUB_SKIP_CONDA_BOOTSTRAP:-0}" == "1" ]]; then
            _conda_manual_help
            exit 1
        fi
        bootstrap_conda || { _conda_manual_help; exit 1; }
        detect_conda
    fi
    if [[ -z "${MAMBA_BIN}" && -z "${CONDA_BIN}" ]]; then
        echo "ERROR: conda/mamba still unavailable after bootstrap." >&2
        _conda_manual_help
        exit 1
    fi
    [[ -n "${MAMBA_BIN}" ]] && echo "mamba: ${MAMBA_BIN}"
    [[ -n "${CONDA_BIN}" ]] && echo "conda: ${CONDA_BIN}"
}

# Detect conda/mamba on PATH, or source one from a common install prefix.
detect_conda() {
    MAMBA_BIN=""; CONDA_BIN=""
    command -v mamba >/dev/null 2>&1 && MAMBA_BIN="$(command -v mamba)"
    command -v conda >/dev/null 2>&1 && CONDA_BIN="$(command -v conda)"
    if [[ -z "${CONDA_BIN}" && -z "${MAMBA_BIN}" ]]; then
        local base
        for base in "${HOME}/miniforge3" "${HOME}/mambaforge" \
                    "${HOME}/miniconda3" "${HOME}/anaconda3"; do
            if [[ -f "${base}/etc/profile.d/conda.sh" ]]; then
                # shellcheck disable=SC1090,SC1091
                source "${base}/etc/profile.d/conda.sh"
                [[ -f "${base}/etc/profile.d/mamba.sh" ]] && \
                    source "${base}/etc/profile.d/mamba.sh"
                command -v conda >/dev/null 2>&1 && CONDA_BIN="$(command -v conda)"
                command -v mamba >/dev/null 2>&1 && MAMBA_BIN="$(command -v mamba)"
                break
            fi
        done
    fi
}

# Download + install Miniforge (conda + mamba, conda-forge default) non-interactively.
bootstrap_conda() {
    local prefix="${CONDA_INSTALL_PREFIX:-${HOME}/miniforge3}"
    local arch url dl
    arch="$(uname -m)"
    url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-${arch}.sh"
    echo
    echo "No conda/mamba found — installing Miniforge to ${prefix} (non-interactive)..."
    echo "  ${url}"
    dl="$(mktemp "${TMPDIR:-/tmp}/miniforge.XXXXXX.sh")"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "${url}" -o "${dl}" || { echo "ERROR: Miniforge download failed." >&2; rm -f "${dl}"; return 1; }
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "${dl}" "${url}" || { echo "ERROR: Miniforge download failed." >&2; rm -f "${dl}"; return 1; }
    else
        echo "ERROR: need 'curl' or 'wget' to download Miniforge." >&2
        rm -f "${dl}"; return 1
    fi
    if ! bash "${dl}" -b -p "${prefix}"; then
        echo "ERROR: Miniforge installation failed." >&2
        rm -f "${dl}"; return 1
    fi
    rm -f "${dl}"
    # Make conda/mamba available for the rest of THIS script...
    # shellcheck disable=SC1091
    source "${prefix}/etc/profile.d/conda.sh"
    [[ -f "${prefix}/etc/profile.d/mamba.sh" ]] && source "${prefix}/etc/profile.d/mamba.sh"
    # ...and persist for the user's future shells.
    conda init bash >/dev/null 2>&1 || true
    echo "Miniforge installed at ${prefix}."
    echo "  (For direct 'conda' use later, open a new terminal or 'source ~/.bashrc'.)"
}

_conda_manual_help() {
    cat <<'EOF'

Could not set up conda automatically. Install Miniforge manually, then re-run:

  curl -fsSL "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh" -o miniforge.sh
  bash miniforge.sh -b -p "$HOME/miniforge3"
  source "$HOME/miniforge3/etc/profile.d/conda.sh"
  bash install_bear.sh

(To skip auto-bootstrap and require a pre-existing conda, set BEAR_HUB_SKIP_CONDA_BOOTSTRAP=1.)
EOF
}

# =============================================================================
# Step 2: setup_bear_hub_env — create the Reflex UI environment
# =============================================================================
setup_bear_hub_env() {
    echo
    echo "=== Step 2: Setting up 'bear-hub' environment (Reflex UI) ==="

    mkdir -p "${ENVS_DIR}"

    # Create the Python base env if missing (Reflex is NOT on conda-forge — it
    # ships on PyPI only — so conda provides Python + conda-available deps).
    if [[ -d "${BEAR_PREFIX}/bin" ]]; then
        echo "Ambiente 'bear-hub' ja existe em: ${BEAR_PREFIX}"
    else
        echo "Criando ambiente 'bear-hub' em ${BEAR_PREFIX}..."
        if [[ -n "${MAMBA_BIN}" ]]; then
            "${MAMBA_BIN}" create -y -p "${BEAR_PREFIX}" -c conda-forge \
                python=3.11 websockets pyyaml
        else
            "${CONDA_BIN}" create -y -p "${BEAR_PREFIX}" -c conda-forge \
                python=3.11 websockets pyyaml
        fi
    fi
    # Ensure Reflex is present and pinned — ALWAYS (idempotent). This fixes
    # partial installs where the env exists but Reflex is missing, and lets
    # update_bear.sh bump Reflex when a release requires a new version. pip is a
    # no-op when reflex==${REFLEX_VERSION} is already satisfied.
    if [[ ! -x "${BEAR_PREFIX}/bin/python" ]]; then
        echo "ERROR: bear-hub env has no python at ${BEAR_PREFIX}/bin/python." >&2
        echo "  The conda env was not created. See errors above; re-run the installer." >&2
        exit 1
    fi
    echo "Ensuring Reflex ${REFLEX_VERSION} (PyPI) in the 'bear-hub' env..."
    "${BEAR_PREFIX}/bin/python" -m pip install "reflex==${REFLEX_VERSION}"

    # ── Ensure a modern Node.js INSIDE the env ────────────────────────────────
    # Reflex's production build compresses the exported frontend by running
    # `node compress-static.js` via `which node` — i.e. the FIRST node on the
    # user's PATH. On a machine whose only node is an EOL system build (e.g.
    # 12.22.x), that step dies with "Failed to compress the exported frontend"
    # and the app never comes up after an update. Ship our own modern node in
    # the env so the build never depends on the user's system node; run.sh puts
    # this env's bin first on PATH so `which node` resolves here. Idempotent:
    # skip when the env already has node >= 20 (avoids a conda re-solve on every
    # update).
    local env_node_major=0
    if [[ -x "${BEAR_PREFIX}/bin/node" ]]; then
        env_node_major="$("${BEAR_PREFIX}/bin/node" -e \
            'console.log(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)"
    fi
    if [[ "${env_node_major:-0}" -lt 20 ]]; then
        echo "Ensuring a modern Node.js (>=20.19) in the 'bear-hub' env..."
        "${MAMBA_BIN:-${CONDA_BIN}}" install -y -p "${BEAR_PREFIX}" \
            -c conda-forge 'nodejs>=20.19'
    else
        echo "Node.js in 'bear-hub' env: $("${BEAR_PREFIX}/bin/node" --version 2>/dev/null) (OK)"
    fi

    # Pre-build the Reflex frontend (.web/) so the first launch is fast.
    # The app already lives in bearhub_rx/ — no `reflex init` needed (that would
    # scaffold a new app). `reflex run` generates .web/ automatically; we just
    # warm it up here so the user's first run isn't a long compile.
    # Launch reflex via `python -m reflex` rather than the bin/reflex shim: pip
    # bakes an absolute interpreter path into the shim's shebang, which breaks if
    # the env is ever moved/cloned to a different path. `python -m` is portable.
    local app_dir="${BEAR_HUB_ROOT}/bearhub_rx"
    if [[ -f "${app_dir}/rxconfig.py" ]]; then
        echo "Pre-compilando frontend Reflex em ${app_dir}/.web ..."
        # Put the env's bin first on PATH so the export's compress step uses the
        # env's modern node (via `which node`), not an old system node.
        ( cd "${app_dir}" && PATH="${BEAR_PREFIX}/bin:${PATH}" \
            "${BEAR_PREFIX}/bin/python" -m reflex export --frontend-only \
            --no-zip --loglevel warning 2>/dev/null ) || \
            echo "  (pre-compile skipped — will build on first run)"
    fi
}

# =============================================================================
# Step 3: setup_bactopia_env — create the Bactopia/Nextflow environment
# =============================================================================
setup_bactopia_env() {
    echo
    echo "=== Step 3: Setting up 'bactopia' environment ==="

    mkdir -p "${ENVS_DIR}"

    # Pin to the validated version (also pulls a compatible Nextflow + JDK,
    # >= 26.04 for 4.x). Check for the actual binary — not just the dir — so a
    # previous partial install (env dir created, package failed) gets repaired.
    local solver="${MAMBA_BIN:-${CONDA_BIN}}"
    if [[ -x "${BACTOPIA_PREFIX}/bin/bactopia" ]]; then
        echo "Ambiente 'bactopia' ja existe em: ${BACTOPIA_PREFIX}"
    elif [[ -d "${BACTOPIA_PREFIX}" ]]; then
        echo "Reparando ambiente 'bactopia' incompleto (bactopia=${BACTOPIA_VERSION})..."
        "${solver}" install -y -p "${BACTOPIA_PREFIX}" \
            -c conda-forge -c bioconda "bactopia=${BACTOPIA_VERSION}"
    else
        echo "Criando ambiente 'bactopia' em ${BACTOPIA_PREFIX} com Bactopia ${BACTOPIA_VERSION}..."
        echo "  (o pipeline sera executado com '-profile docker' pelo BEAR-HUB)"
        "${solver}" create -y -p "${BACTOPIA_PREFIX}" \
            -c conda-forge -c bioconda "bactopia=${BACTOPIA_VERSION}"
        echo "Ambiente 'bactopia' criado em: ${BACTOPIA_PREFIX}"
    fi

    # Ensure nextflow is available inside the bactopia environment
    ensure_nextflow
}

# =============================================================================
# Helper: ensure_nextflow — install Nextflow if missing from bactopia env
# =============================================================================
ensure_nextflow() {
    echo
    echo "Verificando nextflow no ambiente 'bactopia'..."

    if [[ -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo "nextflow ja encontrado em: ${BACTOPIA_PREFIX}/bin/nextflow"
        return 0
    fi

    echo "nextflow nao encontrado em '${BACTOPIA_PREFIX}/bin/nextflow'."
    echo "Tentando instalar nextflow dentro do ambiente 'bactopia'..."

    if [[ -n "${MAMBA_BIN}" ]]; then
        "${MAMBA_BIN}" install -y -p "${BACTOPIA_PREFIX}" \
            -c bioconda -c conda-forge nextflow || true
    else
        "${CONDA_BIN}" install -y -p "${BACTOPIA_PREFIX}" \
            -c bioconda -c conda-forge nextflow || true
    fi

    # If conda/mamba install didn't produce the binary, download directly
    if [[ ! -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo
        echo "ATENCAO: 'nextflow' ainda nao foi encontrado."
        echo "Baixando nextflow pelo script oficial (get.nextflow.io)..."

        mkdir -p "${BACTOPIA_PREFIX}/bin"

        if command -v curl >/dev/null 2>&1; then
            curl -fsSL https://get.nextflow.io -o "${BACTOPIA_PREFIX}/bin/nextflow"
        elif command -v wget >/dev/null 2>&1; then
            wget -qO "${BACTOPIA_PREFIX}/bin/nextflow" https://get.nextflow.io
        else
            echo
            echo "ERRO: nem 'curl' nem 'wget' encontrados para baixar nextflow."
            echo "Instale 'curl' ou 'wget' e rode novamente 'install_bear.sh',"
            echo "ou instale manualmente o binario em '${BACTOPIA_PREFIX}/bin/nextflow'."
            exit 1
        fi

        chmod +x "${BACTOPIA_PREFIX}/bin/nextflow"
    fi

    # Final check
    if [[ -x "${BACTOPIA_PREFIX}/bin/nextflow" ]]; then
        echo "nextflow disponivel em: ${BACTOPIA_PREFIX}/bin/nextflow"
    else
        echo
        echo "ERRO: nao foi possivel garantir um 'nextflow' utilizavel."
        echo "Verifique a instalacao do ambiente 'bactopia' e rode o instalador novamente."
        exit 1
    fi
}

# =============================================================================
# Step 4: write_config — persist config.env for the Reflex app
# =============================================================================
write_config() {
    echo
    echo "=== Step 4: Writing configuration ==="

    mkdir -p "${CONFIG_DIR}"
    mkdir -p "${DATA_DIR}"
    mkdir -p "${OUT_DIR}"

    # Determine NXF_CONDA_EXE (mamba preferred)
    local nxf_solver=""
    if [[ -n "${MAMBA_BIN}" ]]; then
        nxf_solver="${MAMBA_BIN}"
        echo "NXF_CONDA_EXE sera configurado para usar: ${nxf_solver}"
    else
        echo "AVISO: mamba nao encontrado, NXF_CONDA_EXE nao sera definido."
    fi

    {
        echo "# Generated by install_bear.sh — edit to change default directories."
        echo "# This file is read by BEAR-HUB at startup (utils/system.py)."
        echo
        echo "export BEAR_HUB_ROOT=\"${BEAR_HUB_ROOT}\""
        echo "export BEAR_HUB_BASEDIR=\"${DATA_DIR}\""
        echo "export BEAR_HUB_OUTDIR=\"${OUT_DIR}\""
        echo "export BEAR_HUB_DATA=\"${DATA_DIR}\""
        echo
        echo "# Bactopia conda environment (provides Nextflow)"
        echo "export BACTOPIA_ENV_PREFIX=\"${BACTOPIA_PREFIX}\""
        if [[ -n "${nxf_solver}" ]]; then
            echo "export NXF_CONDA_EXE=\"${nxf_solver}\""
        else
            echo "# NXF_CONDA_EXE nao definido (mamba nao encontrado)"
        fi
        echo
        echo "# Pinned Bactopia version used during installation"
        echo "export BACTOPIA_VERSION=\"${BACTOPIA_VERSION}\""
    } > "${CONFIG_FILE}"

    echo "Config salva em: ${CONFIG_FILE}"
}

# =============================================================================
# Step 5: configure_reflex — disable Reflex telemetry
# =============================================================================
configure_reflex() {
    echo
    echo "=== Step 5: Configuring Reflex ==="
    # Disable Reflex telemetry / analytics
    export TELEMETRY_ENABLED=false
    local rx_dir="${HOME}/.reflex"
    mkdir -p "${rx_dir}"
    local rx_cfg="${rx_dir}/config.json"
    if [[ ! -f "${rx_cfg}" ]]; then
        echo '{"telemetry_enabled": false}' > "${rx_cfg}"
        echo "Reflex telemetry disabled."
    else
        echo "${rx_cfg} already exists — skipping."
    fi
}

# =============================================================================
# Step 6: verify_install — post-install smoke test of every runtime dependency
# =============================================================================
verify_install() {
    echo
    echo "=== Step 6: Verifying installation ==="
    local ok=0 warn=0 fail=0
    local nf="${BACTOPIA_PREFIX}/bin/nextflow"
    local jv="${BACTOPIA_PREFIX}/bin/java"

    # Reflex (bear-hub env). Exercise the ACTUAL launch path used by run.sh —
    # `python -m reflex` — not just `import reflex`, so a usable CLI is confirmed
    # (the bin/reflex shim can be broken by an absolute-path shebang).
    if "${BEAR_PREFIX}/bin/python" -m reflex --version >/dev/null 2>&1; then
        local rxver
        rxver=$("${BEAR_PREFIX}/bin/python" -m reflex --version 2>/dev/null | head -1)
        echo "  [OK]   Reflex CLI runnable (${rxver:-unknown})"; ok=$((ok+1))
    elif "${BEAR_PREFIX}/bin/python" -c "import reflex" >/dev/null 2>&1; then
        echo "  [WARN] Reflex imports but 'python -m reflex' failed in ${BEAR_PREFIX}"; warn=$((warn+1))
    else
        echo "  [FAIL] Reflex not runnable in ${BEAR_PREFIX}"; fail=$((fail+1))
    fi

    # Java (Nextflow requires a JDK — normally pulled in by the bactopia conda env)
    if [[ -x "${jv}" ]] && "${jv}" -version >/dev/null 2>&1; then
        echo "  [OK]   Java (env): $("${jv}" -version 2>&1 | head -1)"; ok=$((ok+1))
    elif command -v java >/dev/null 2>&1; then
        echo "  [OK]   Java (system): $(java -version 2>&1 | head -1)"; ok=$((ok+1))
    else
        echo "  [FAIL] Java not found — Nextflow cannot run. Install a JDK (>=17)."; fail=$((fail+1))
    fi

    # Nextflow
    if [[ -x "${nf}" ]] && "${nf}" -version >/dev/null 2>&1; then
        echo "  [OK]   Nextflow: $("${nf}" -version 2>&1 | grep -i version | head -1 | tr -s ' ')"; ok=$((ok+1))
    else
        echo "  [FAIL] Nextflow not runnable at ${nf}"; fail=$((fail+1))
    fi

    # Bactopia
    if "${BACTOPIA_PREFIX}/bin/bactopia" --version >/dev/null 2>&1; then
        echo "  [OK]   Bactopia: $("${BACTOPIA_PREFIX}/bin/bactopia" --version 2>&1 | head -1)"; ok=$((ok+1))
    else
        echo "  [WARN] Bactopia CLI not verifiable (the pipeline runs via Nextflow regardless)"; warn=$((warn+1))
    fi

    # Docker daemon (runtime requirement, not a build dep → warning)
    if docker info >/dev/null 2>&1; then
        echo "  [OK]   Docker daemon reachable"; ok=$((ok+1))
    else
        echo "  [WARN] Docker daemon not reachable — start it before running analyses"; warn=$((warn+1))
    fi

    echo
    echo "  Summary: ${ok} OK, ${warn} warning(s), ${fail} failure(s)"
    if [[ ${fail} -gt 0 ]]; then
        echo "  ✗ Installation has failures above — BEAR-HUB will not run until fixed."
        return 1
    fi
    echo "  ✓ Core dependencies verified."
    return 0
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo "======================================="
    echo "  BEAR-HUB Installer"
    echo "  Bactopia version: ${BACTOPIA_VERSION}"
    echo "======================================="
    echo "BEAR_HUB_ROOT : ${BEAR_HUB_ROOT}"
    echo "DATA_DIR      : ${DATA_DIR}"
    echo "OUT_DIR       : ${OUT_DIR}"
    echo "CONFIG_FILE   : ${CONFIG_FILE}"

    check_prerequisites
    setup_bear_hub_env
    setup_bactopia_env
    write_config
    configure_reflex

    local verify_rc=0
    verify_install || verify_rc=$?

    echo
    echo "======================================="
    if [[ ${verify_rc} -eq 0 ]]; then
        echo "  Installation complete!"
    else
        echo "  Installation finished WITH ERRORS (see Step 6)"
    fi
    echo "======================================="
    echo
    echo "Next steps:"
    echo "  source \"${CONFIG_FILE}\""
    echo "  bash \"${BEAR_HUB_ROOT}/bearhub_rx/run.sh\""
    echo
    echo "Or manually:"
    echo "  cd \"${BEAR_HUB_ROOT}/bearhub_rx\""
    echo "  \"${BEAR_PREFIX}/bin/python\" -m reflex run"
    echo
    echo "Bactopia will run via '-profile docker' — make sure Docker is running."
    echo
    echo "Optional — pre-download Bactopia datasets (genome sizes, species DBs):"
    echo "  conda run -p \"${BACTOPIA_PREFIX}\" bactopia datasets --help"
    echo "  (not required for the core pipeline; enables species-specific features)"
}

main "$@"
