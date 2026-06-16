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
	@echo "  make run        Launch the Reflex app via bearhub_rx/run.sh"
	@echo "  make update     Safely update (stash + pull + reinstall) via update_bear.sh"
	@echo "  make uninstall  Remove BEAR-HUB conda envs and config"
	@echo "  make test       Run the pytest test suite in the bear-hub env"
	@echo "  make lint       Run flake8 on the Python source files"
	@echo ""
	@echo "Override Bactopia version:"
	@echo "  make install BACTOPIA_VERSION=4.0.0"

# ── Install / setup ───────────────────────────────────────────────────────────
install:
	BACTOPIA_VERSION="$${BACTOPIA_VERSION:-4.0.0}" bash install_bear.sh

# ── Run application ───────────────────────────────────────────────────────────
run:
	bash bearhub_rx/run.sh

# ── Update (safe pull + reinstall via update_bear.sh) ─────────────────────────
# Stashes local changes, fast-forwards, re-runs the installer (keeping the
# installed Bactopia pin), and clears the stale Reflex frontend.
update:
	bash update_bear.sh

# ── Uninstall ─────────────────────────────────────────────────────────────────
uninstall:
	bash uninstall_bear.sh

# ── Tests ─────────────────────────────────────────────────────────────────────
# The suite lives in bearhub_rx/tests/ as standalone scripts (custom check()
# harness, not pytest) — run them with the bear-hub env's Python.
BEAR_PY ?= $(shell ls envs/bear-hub/bin/python 2>/dev/null || command -v python3)

test:
	@if [ -z "$(BEAR_PY)" ]; then \
		echo "ERROR: bear-hub env Python not found. Run 'make install' first."; \
		exit 1; \
	fi
	$(BEAR_PY) bearhub_rx/tests/test_unit.py

# ── Lint ──────────────────────────────────────────────────────────────────────
# flake8 is optional; skip cleanly if it isn't installed in the env.
lint:
	@if [ -x envs/bear-hub/bin/flake8 ]; then \
		envs/bear-hub/bin/flake8 bearhub_rx/bearhub --max-line-length=120 --extend-ignore=E501; \
	elif command -v flake8 >/dev/null 2>&1; then \
		flake8 bearhub_rx/bearhub --max-line-length=120 --extend-ignore=E501; \
	else \
		echo "flake8 not installed — skipping lint. (pip install flake8 in the bear-hub env to enable.)"; \
	fi
