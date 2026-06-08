# Source Generated with Decompyle++
# File: runner.cpython-311.pyc (Python 3.11)

"""
Async Nextflow runner for the Reflex app.

`stream()` is an async generator: it launches the command, reads stdout, and
pushes cleaned log lines into a Reflex state via `async with state:`. The caller
(a Reflex `@rx.event(background=True)`) drives it and `yield`s to flush updates
to the browser. Kept Reflex-import-free — it only relies on the state object's
async context manager and plain attributes (`log`, `status`, `running`).
"""
from __future__ import annotations
import asyncio
import hashlib
import os
import re
import shlex
import shutil
from bearhub.core.system import APP_STATE_DIR, get_bactopia_version, get_nextflow_bin
_PROCS: 'dict[str, asyncio.subprocess.Process]' = { }
MAX_LOG_LINES = 1500
_ANSI = re.compile('\\x1B\\[[0-?]*[ -/]*[@-~]')

def _resolve_cursor_up(text = None):
    parts = re.split('\\x1b\\[(\\d+)A', text)
    lines = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            lines.extend(part.split('\n'))
            continue
        del lines[-int(part):]
        return '\n'.join(lines)


def normalize_chunk(chunk = None):
    if not chunk:
        return []
    chunk = None(chunk)
    chunk = _ANSI.sub('', chunk).replace('\r', '\n')
    chunk = re.sub('\\s+-\\s+\\[', '\n[', chunk)
    chunk = re.sub('(?<!^)\\s+(?=executor\\s*>)', '\n', chunk, flags = re.IGNORECASE)
    return chunk.split('\n')()


def write_include_file(outdir = None, samples = None):
    '''One sample name per line, for Bactopia Tools `--include`.'''
    APP_STATE_DIR.mkdir(parents = True, exist_ok = True)
    digest = hashlib.md5((outdir + '|' + ';'.join(samples)).encode()).hexdigest()[:10]
    fname = APP_STATE_DIR / f'''include_{digest}.txt'''
    fname.write_text('\n'.join(samples) + '\n', encoding = 'utf-8')
    return str(fname)


def nextflow_wf_cmd(wf, outdir, include_file, profile, threads, memory_gb = None, resume = None, tool_args = None, global_extra = ('wf', 'str', 'outdir', 'str', 'include_file', 'str', 'profile', 'str', 'threads', 'int', 'memory_gb', 'int', 'resume', 'bool', 'tool_args', 'list[str]', 'global_extra', 'str', 'return', 'str')):
    """
    Bactopia 4.0 tool command. Tools keep the `--bactopia <results> --include`
    model, but must be launched via the tool's own main.nf (`-main-script`) —
    the top-level `--wf` entry doesn't declare `--bactopia`/`--include`, so
    Nextflow 26's strict validation rejects them there.
    """
    base = [
        get_nextflow_bin(),
        'run',
        'bactopia/bactopia']
    ver = get_bactopia_version()
    if ver:
        base += [
            '-r',
            f'''v{ver}''']
    base += [
        '-main-script',
        f'''workflows/bactopia-tools/{wf}/main.nf''',
        '-profile',
        profile,
        '--bactopia',
        outdir]
    if include_file:
        base += [
            '--include',
            include_file]
    if threads > 0:
        base += [
            '--max_cpus',
            str(threads)]
    if memory_gb > 0:
        base += [
            '--max_memory',
            f'''{memory_gb}.GB''']
    if resume:
        base += [
            '-resume']
    base += tool_args
    if global_extra.strip():
        base += shlex.split(global_extra)
    return (lambda .0: pass# WARNING: Decompyle incomplete
)(base())


def join_subcommands(labelled = None):
    """labelled: list of (banner, command) -> a single ';'-joined shell line."""
    stdbuf = shutil.which('stdbuf')
    parts = []
    for banner, cmd in labelled:
        if stdbuf:
            cmd = f'''{stdbuf} -oL -eL {cmd}'''
        parts.append(f'''echo "===== {banner} =====" ; {cmd}''')
        return ' ; '.join(parts)


def stream(state = None, cmd = None, ns = None, work_dir = (None,)):
    """
    Run *cmd*, streaming normalized output into state.log. Async generator:
    yields after each batch so the calling background event can flush.

    *work_dir* sets the subprocess cwd so Nextflow writes its `.nextflow.log`,
    `.nextflow/` and `work/` OUTSIDE the Reflex app directory — otherwise the
    dev hot-reloader sees those writes and reloads, killing the run's worker.
    """
    pass
# WARNING: Decompyle incomplete


async def stop(ns = None):
    pass
# WARNING: Decompyle incomplete

