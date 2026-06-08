# Source Generated with Decompyle++
# File: system.cpython-310.pyc (Python 3.10)

'''
System / environment detection (self-contained, no Streamlit/Reflex deps).

Resolves the Nextflow binary and bootstraps BEAR-HUB env vars from the same
config files the legacy launcher uses, so the Reflex app works with an existing
install_bear.sh setup unchanged.
'''
from __future__ import annotations
import os
import pathlib
import re
import shutil
import subprocess
APP_STATE_DIR = pathlib.Path.home() / '.bactopia_ui_local'
_bactopia_version_cache: 'str | None' = None
_CONFIG_DIR = pathlib.Path.home() / '.bear-hub'
_LEGACY_CONFIG = pathlib.Path.home() / 'BEAR-HUB' / '.bear-hub.env'

def which(cmd = None):
    return shutil.which(cmd)


def get_nextflow_bin():
