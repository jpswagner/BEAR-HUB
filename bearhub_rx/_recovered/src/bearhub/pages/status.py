# Source Generated with Decompyle++
# File: status.cpython-311.pyc (Python 3.11)

'''Status page — installed versions.'''
from __future__ import annotations
import reflex as rx
from bearhub.components.shell import shell
from bearhub.components.wizard import hero
from bearhub.data.catalog import BACTOPIA_VERSION
from bearhub.state import StatusState
_ROWS = [
    ('Bactopia', 'bactopia'),
    ('Nextflow', 'nextflow'),
    ('Java', 'java'),
    ('Docker', 'docker')]

def _version_row(label = None, key = None):
    return rx.hstack(rx.text(label, weight = 'bold', size = '2', width = '120px'), rx.code(StatusState.versions.get(key, 'Unknown')), spacing = '3', align = 'center', width = '100%')


def status_page():
    pass
# WARNING: Decompyle incomplete

