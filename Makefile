# BEAR-HUB Makefile
# ---------------------------------------------------------------------------
# Common development and deployment tasks.
# Assumes the bear-hub conda environment was created by install_bear.sh.
# ---------------------------------------------------------------------------

.PHONY: install run update uninstall test lint help

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo "BEAR-HUB Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  make install    Run install_bear.sh (creates conda envs, writes config)"
	@echo "  make run        Launch the Streamlit app via run_bear.sh"
	@echo "  make update     Pull latest code and re-run install_bear.sh"
	@echo "  make uninstall  Remove BEAR-HUB conda envs and config"
	@echo "  make test       Run the pytest test suite in the bear-hub env"
	@echo "  make lint       Run flake8 on the Python source files"
	@echo ""
	@echo "Override Bactopia version:"
	@echo "  make install BACTOPIA_VERSION=3.1.0"

# ── Install / setup ───────────────────────────────────────────────────────────
install:
	BACTOPIA_VERSION="$${BACTOPIA_VERSION:-3.0.0}" bash install_bear.sh

# ── Run application ───────────────────────────────────────────────────────────
run:
	bash run_bear.sh

# ── Update (pull + reinstall) ─────────────────────────────────────────────────
update:
	git pull --ff-only
	BACTOPIA_VERSION="$${BACTOPIA_VERSION:-3.0.0}" bash install_bear.sh

# ── Uninstall ─────────────────────────────────────────────────────────────────
uninstall:
	bash uninstall_bear.sh

# ── Tests ─────────────────────────────────────────────────────────────────────
# Uses conda run so that the streamlit package is available during import.
CONDA_BIN ?= $(shell command -v conda 2>/dev/null || command -v mamba 2>/dev/null)

test:
	@if [ -z "$(CONDA_BIN)" ]; then \
		echo "ERROR: conda/mamba not found in PATH. Activate the environment manually:"; \
		echo "  conda activate bear-hub && pytest tests/ -v"; \
		exit 1; \
	fi
	$(CONDA_BIN) run -n bear-hub pytest tests/ -v --tb=short

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	@if [ -z "$(CONDA_BIN)" ]; then \
		flake8 utils/ constants.py pages/ BEAR-HUB.py --max-line-length=120; \
	else \
		$(CONDA_BIN) run -n bear-hub flake8 utils/ constants.py pages/ BEAR-HUB.py \
			--max-line-length=120 --extend-ignore=E501; \
	fi
