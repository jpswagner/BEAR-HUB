#!/usr/bin/env bash
set -u

APP_NAME="BEAR-HUB"
CONFIG_DIR="${HOME}/BEAR-HUB"
DESKTOP_FILE="${HOME}/.local/share/applications/bear-hub.desktop"
ICON_FILE="${HOME}/.local/share/icons/hicolor/256x256/apps/bear-hub.png"

echo "==========================================="
echo "   Uninstall ${APP_NAME}"
echo "==========================================="
echo
echo "This script will remove:"
echo "1. Desktop shortcut and icon"
echo "2. Configuration folder: ${CONFIG_DIR}"
echo "   (Includes logs, config, and installer setup)"
echo "3. Conda environment: 'bactopia' (Optional)"
echo "4. Temporary AppImage mount points (Cleanup)"
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
echo "--- Cleaning Temporary Mounts ---"
# Be careful here. We look for /tmp/.mount_BEAR-* owned by user.
# find /tmp -maxdepth 1 -name ".mount_BEAR-*" -user "$USER" -type d
FOUND_MOUNTS=$(find /tmp -maxdepth 1 -name ".mount_BEAR-*" -user "$USER" -type d 2>/dev/null)

if [ -n "$FOUND_MOUNTS" ]; then
    echo "Found stale AppImage mounts:"
    echo "$FOUND_MOUNTS"
    echo "Attempting to unmount/remove..."
    for mnt in $FOUND_MOUNTS; do
        # Try fusermount -u first
        fusermount -u -z "$mnt" 2>/dev/null || true
        # If still exists, try rm -rf (risky but necessary for stale mounts)
        if [ -d "$mnt" ]; then
             rm -rf "$mnt"
        fi
    done
    echo "Cleanup complete."
else
    echo "No stale mounts found."
fi


echo
echo "--- Removing Desktop Integration ---"
if [ -f "$DESKTOP_FILE" ]; then
    rm -v "$DESKTOP_FILE"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "${HOME}/.local/share/applications"
    fi
else
    echo "Desktop file not found (already removed?)"
fi

if [ -f "$ICON_FILE" ]; then
    rm -v "$ICON_FILE"
else
    echo "Icon file not found."
fi

echo
echo "--- Checking Conda Environment ---"
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
            echo "Skipping conda environment removal."
        fi
    else
        echo "Environment 'bactopia' not found."
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
echo "You can now delete the .AppImage file manually."
echo
read -p "Press Enter to exit..."
