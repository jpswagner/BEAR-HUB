#!/usr/bin/env bash
set -u

APP_NAME="BEAR-HUB"
CONFIG_DIR="${HOME}/BEAR-HUB"
echo "==========================================="
echo "   Uninstall ${APP_NAME}"
echo "==========================================="
echo
echo "This script will remove:"
echo "1. Configuration folder: ${CONFIG_DIR}"
echo "   (Includes logs, config, and installer setup)"
echo "2. Conda environment: 'bactopia' (Optional)"
echo "3. Conda environment: 'bear-hub' (Optional)"
echo

read -p "Are you sure you want to uninstall BEAR-HUB? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo
echo "--- Stopping running instances ---"
if pgrep -f "bear-hub" >/dev/null; then
    echo "Found running instances of bear-hub. Stopping them..."
    pkill -f "bear-hub" || true
    sleep 2
else
    echo "No running instances found."
fi

echo
echo "--- Checking Conda Environments ---"
CONDA_BIN=""
if command -v mamba >/dev/null 2>&1; then
    CONDA_BIN="mamba"
elif command -v conda >/dev/null 2>&1; then
    CONDA_BIN="conda"
fi

if [ -n "$CONDA_BIN" ]; then
    if $CONDA_BIN env list | grep -q "^bactopia "; then
        echo "Found conda environment 'bactopia'."
        read -p "Do you want to DELETE the 'bactopia' environment? (Type 'delete' to confirm): " confirm
        if [[ "$confirm" == "delete" ]]; then
            $CONDA_BIN env remove -n bactopia -y
            echo "Environment 'bactopia' removed."
        else
            echo "Skipping 'bactopia' environment removal."
        fi
    else
        echo "Environment 'bactopia' not found."
    fi

    echo
    if $CONDA_BIN env list | grep -q "^bear-hub "; then
        echo "Found conda environment 'bear-hub'."
        read -p "Do you want to DELETE the 'bear-hub' environment? (Type 'delete' to confirm): " confirm
        if [[ "$confirm" == "delete" ]]; then
            $CONDA_BIN env remove -n bear-hub -y
            echo "Environment 'bear-hub' removed."
        else
            echo "Skipping 'bear-hub' environment removal."
        fi
    else
        echo "Environment 'bear-hub' not found."
    fi
else
    echo "Conda/Mamba not found, skipping environment cleanup."
fi

echo
echo "--- Removing Config Directory ---"
if [ -d "$CONFIG_DIR" ]; then
    echo "Directory: ${CONFIG_DIR}"
    echo "WARNING: This folder might contain your 'bactopia_out' results if you kept them default."
    read -p "Do you want to DELETE '${CONFIG_DIR}' and ALL content? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "Directory removed."
    else
        echo "Skipping directory removal."
    fi
else
    echo "Directory not found."
fi

echo
echo "==========================================="
echo "   Uninstallation Complete"
echo "==========================================="
echo "You can now delete the BEAR-HUB repository directory manually."
echo
read -p "Press Enter to exit..."
