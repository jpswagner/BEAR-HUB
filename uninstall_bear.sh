#!/usr/bin/env bash
set -u

APP_NAME="BEAR-HUB"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==========================================="
echo "   Uninstall ${APP_NAME}"
echo "==========================================="
echo
echo "This script will help you remove BEAR-HUB."
echo "Since the environments ('bear-hub' and 'bactopia') are now"
echo "installed locally inside the ${ROOT_DIR}/envs folder,"
echo "removing the BEAR-HUB directory will clean up everything at once."
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
echo "--- Removing BEAR-HUB Directory ---"
if [ -d "$ROOT_DIR" ]; then
    echo "Directory: ${ROOT_DIR}"
    echo "WARNING: This folder contains your isolated conda environments, config files,"
    echo "and might contain your 'bactopia_out' results if you kept them default."
    read -p "Do you want to DELETE '${ROOT_DIR}' and ALL its content? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$ROOT_DIR"
        echo "Directory and local environments removed successfully."
    else
        echo "Skipping directory removal."
        echo "You can manually delete the repository later to free up space."
    fi
else
    echo "Directory not found."
fi

echo
echo "==========================================="
echo "   Uninstallation Complete"
echo "==========================================="
echo
