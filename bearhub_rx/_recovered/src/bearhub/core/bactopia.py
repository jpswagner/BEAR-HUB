# Source Generated with Decompyle++
# File: bactopia.cpython-310.pyc (Python 3.10)

'''Bactopia filesystem helpers: sample discovery + directory listing.'''
from __future__ import annotations
import os
import pathlib
from bearhub.core.system import get_default_outdir

def discover_samples(outdir = None):
    '''List sample folders in a Bactopia output directory.'''
    if not outdir:
        pass
    p = pathlib.Path('')
    if not p.is_dir():
        return []
    strict = None
    loose = []
    for child in sorted(p.iterdir(), (lambda x: x.name), **('key',)):
        if not child.is_dir():
            continue
        if child.name.startswith('bactopia-') or child.name in frozenset({'.nextflow', 'bactopia-runs', 'work'}):
            continue
        loose.append(child.name)
        if (child / 'main').exists() or (child / 'tools').exists():
            strict.append(child.name)
    if strict:
        return strict


def guess_root_default():
    '''First existing Bactopia outdir with samples, else the default.'''
    candidates = []
    env_out = os.getenv('BEAR_HUB_OUTDIR')
    if env_out:
        candidates.append(pathlib.Path(env_out).expanduser())
    base = os.getenv('BEAR_HUB_BASEDIR', os.getcwd())
    candidates.append(pathlib.Path(base).expanduser() / 'bactopia_out')
    candidates.append(pathlib.Path.home() / 'BEAR_DATA' / 'bactopia_out')
# WARNING: Decompyle incomplete


def list_subdirs(path = None):
    '''Visible subdirectory names (for the directory picker).'''
    pass
# WARNING: Decompyle incomplete


def safe_dir(path = None):
    '''Resolve to an existing directory, falling back to $HOME.'''
    pass
# WARNING: Decompyle incomplete

