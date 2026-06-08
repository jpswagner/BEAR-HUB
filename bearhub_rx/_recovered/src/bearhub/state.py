# Source Generated with Decompyle++
# File: state.cpython-310.pyc (Python 3.10)

__doc__ = '\nReflex state for BEAR-HUB.\n\nA shared `WizardMixin` carries the bits every guided page needs (step nav,\noutput directory + directory-picker, sample selection, general Nextflow params,\nand the live runner log/status). Concrete page states add their tool selection\nand a background `run` event that builds the command and streams output.\n'
from __future__ import annotations
import os
import reflex as rx
from bearhub.core import bactopia, runner, system
from bearhub.data import catalog

def _to_int(v = None):
    pass
# WARNING: Decompyle incomplete

WizardMixin = <NODE:27>((lambda : step: 'int' = 0outdir: 'str' = ''samples: 'list[str]' = []selected: 'list[str]' = []profile: 'str' = 'docker'threads: 'int' = 0memory: 'int' = 0resume: 'bool' = Trueextra: 'str' = ''picker_open: 'bool' = Falsepicker_cur: 'str' = ''picker_dirs: 'list[str]' = []picker_target: 'str' = 'outdir'log: 'list[str]' = []status: 'str' = 'idle'running: 'bool' = Falsemerged: 'list[str]' = []merged_dir: 'str' = ''
def next_step(self):
self.step += 1
def prev_step(self):
if self.step > 0:
self.step -= 1None
def goto(self = None, i = None):
self.step = i
def init_outdir(self):
if not self.outdir:
self.outdir = bactopia.guess_root_default()self.scan()None
def scan(self):
d = bactopia.safe_dir(self.outdir)self.outdir = dself.samples = bactopia.discover_samples(d)self.selected = list(self.samples)
def toggle_sample(self = None, name = None):
if name in self.selected:
self.selected = (lambda .0 = None: [ s for s in .0 if s != name ])(self.selected)
            return None
        self.selected = None.selected + [
            name]

def select_all_samples(self):
self.selected = list(self.samples)
def clear_samples(self):
self.selected = []
def set_profile(self = None, v = None):
self.profile = v
def set_threads(self, v):
if isinstance(v, (list, tuple)):
v = v[0] if v else 0self.threads = _to_int(v)
def set_memory(self, v):
if isinstance(v, (list, tuple)):
v = v[0] if v else 0self.memory = _to_int(v)
def set_resume(self = None, v = None):
self.resume = bool(v)
def set_extra(self = None, v = None):
self.extra = v
def open_picker_for(self = None, target = None):
self.picker_target = targetif not getattr(self, target, ''):
passself.picker_cur = bactopia.safe_dir(self.outdir)self.picker_dirs = bactopia.list_subdirs(self.picker_cur)self.picker_open = True
def open_picker(self):
self.open_picker_for('outdir')
def set_picker_open(self = None, v = None):
self.picker_open = bool(v)
def picker_enter(self = None, name = None):
self.picker_cur = bactopia.safe_dir(os.path.join(self.picker_cur, name))self.picker_dirs = bactopia.list_subdirs(self.picker_cur)
def picker_up(self):
self.picker_cur = bactopia.safe_dir(os.path.dirname(self.picker_cur))self.picker_dirs = bactopia.list_subdirs(self.picker_cur)
def picker_home(self):
self.picker_cur = bactopia.safe_dir(os.path.expanduser('~'))self.picker_dirs = bactopia.list_subdirs(self.picker_cur)
def picker_select(self):
setattr(self, self.picker_target, self.picker_cur)self.picker_open = Falseif self.picker_target == 'outdir':
self.samples = bactopia.discover_samples(self.outdir)self.selected = list(self.samples)None
def refresh_merged(self):
import pathlibself.merged = []self.merged_dir = ''out = bactopia.safe_dir(self.outdir)runs = pathlib.Path(out) / 'bactopia-runs'if not runs.is_dir():
Nonesubs = None((lambda .0: [ p for p in .0 if p.is_dir() ])(runs.glob('*')))
        if not subs:
            return None
        mr = None[-1] / 'merged-results'
        if mr.is_dir():
            self.merged_dir = str(mr)
            self.merged = (lambda .0: [ f.name for f in .0 ])(sorted(mr.glob('*.tsv')))
            return None

def n_selected(self = None):
len(self.selected)n_selected = None(n_selected)
def n_samples(self = None):
len(self.samples)n_samples = None(n_samples)
def has_samples(self = None):
len(self.samples) > 0has_samples = None(has_samples)
def status_label(self = None):
{
'running': 'Running…',
'success': 'Finished successfully',
'failed': 'Run failed — check the log',
'stopped': 'Stopped by user',
'idle': '' }.get(self.status, self.status)status_label = None(status_label)
def status_color(self = None):
{
'running': 'blue',
'success': 'green',
'failed': 'red',
'stopped': 'amber',
'idle': 'gray' }.get(self.status, 'gray')status_color = None(status_color)
def log_text(self = None):
'\n'.join(self.log)log_text = None(log_text)), 'WizardMixin', rx.State, True, **('mixin',))

class ToolsState(rx.State, WizardMixin):
    picks: 'dict[str, bool]' = { }
    opts: 'dict[str, str]' = dict(catalog.DEFAULT_OPTS)
    flags: 'dict[str, bool]' = dict(catalog.DEFAULT_FLAGS)
    
    def toggle(self = None, tid = None):
        self.picks[tid] = not self.picks.get(tid, False)

    
    def set_opt(self = None, key = None, value = None):
        self.opts[key] = str(value)

    
    def set_flag(self = None, key = None, value = None):
        self.flags[key] = bool(value)

    
    def picked_ids(self = None):
        return (lambda .0: [ t for t, on in .0 if on ])(self.picks.items())

    picked_ids = None(picked_ids)
    
    def n_picked(self = None):
        return len(self.picked_ids)

    n_picked = None(n_picked)
    
    def picked_detailed(self = None):
        return (lambda .0: [ t for t in .0 if t in catalog.DETAILED ])(self.picked_ids)

    picked_detailed = None(picked_detailed)
    
    def preview(self = None):
        lines = []
        for tid in self.picked_ids:
            args = catalog.build_tool_args(tid, self.opts, self.flags)
            if not self.outdir:
                pass
            if not self.threads:
                pass
            if not self.memory:
                pass
            lines.append(runner.nextflow_wf_cmd(tid, '<outdir>', '<include-file>', self.profile, int(0), int(0), bool(self.resume), args, self.extra))
        if not '\n\n'.join(lines):
            pass
        return '# select at least one tool'

    preview = None(preview)
    
    def _build(self):
        if not system.nextflow_available():
            return ('', 'Nextflow not found (PATH / BACTOPIA_ENV_PREFIX / NEXTFLOW_BIN).')
        outdir = None.safe_dir(self.outdir)
        if not list(self.selected):
            pass
        samples = list(self.samples)
        if not samples:
            return ('', 'Select at least one sample.')
        picked = None.picked_ids
        if not picked:
            return ('', 'Select at least one tool.')
        inc = None.write_include_file(outdir, samples)
        labelled = []
        for tid in picked:
            args = catalog.build_tool_args(tid, self.opts, self.flags)
            if not self.threads:
                pass
            if not self.memory:
                pass
            cmd = runner.nextflow_wf_cmd(tid, outdir, inc, self.profile, int(0), int(0), bool(self.resume), args, self.extra)
            labelled.append((f'''[Bactopia Tool] {tid}''', cmd))
        return (runner.join_subcommands(labelled), '')

    
    def run(self):
        pass
    # WARNING: Decompyle incomplete

    run = rx.event(True, **('background',))(run)
    
    async def stop_run(self):
        await runner.stop('tools')
    # WARNING: Decompyle incomplete

    stop_run = rx.event(True, **('background',))(stop_run)


class MerlinState(rx.State, WizardMixin):
    picks: 'dict[str, bool]' = (lambda .0: pass# WARNING: Decompyle incomplete
)(catalog.MERLIN_WF_IDS)
    
    def toggle(self = None, wf = None):
        self.picks[wf] = not self.picks.get(wf, False)

    
    def picked_ids(self = None):
        return (lambda .0: [ w for w, on in .0 if on ])(self.picks.items())

    picked_ids = None(picked_ids)
    
    def n_picked(self = None):
        return len(self.picked_ids)

    n_picked = None(n_picked)
    
    def preview(self = None):
        lines = []
        for wf in self.picked_ids:
            if not self.outdir:
                pass
            if not self.threads:
                pass
            if not self.memory:
                pass
            lines.append(runner.nextflow_wf_cmd(wf, '<outdir>', '<include-file>', self.profile, int(0), int(0), bool(self.resume), [], self.extra))
        if not '\n\n'.join(lines):
            pass
        return '# select at least one species tool'

    preview = None(preview)
    
    def _build(self):
        if not system.nextflow_available():
            return ('', 'Nextflow not found (PATH / BACTOPIA_ENV_PREFIX / NEXTFLOW_BIN).')
        outdir = None.safe_dir(self.outdir)
        if not list(self.selected):
            pass
        samples = list(self.samples)
        if not samples:
            return ('', 'Select at least one sample.')
        picked = None.picked_ids
        if not picked:
            return ('', 'Select at least one species-specific tool.')
        inc = None.write_include_file(outdir, samples)
        labelled = []
        for wf in picked:
            if not self.threads:
                pass
            if not self.memory:
                pass
            cmd = runner.nextflow_wf_cmd(wf, outdir, inc, self.profile, int(0), int(0), bool(self.resume), [], self.extra)
            labelled.append((f'''[Bactopia Species] {wf}''', cmd))
        return (runner.join_subcommands(labelled), '')

    
    def run(self):
        pass
    # WARNING: Decompyle incomplete

    run = rx.event(True, **('background',))(run)
    
    async def stop_run(self):
        await runner.stop('merlin')
    # WARNING: Decompyle incomplete

    stop_run = rx.event(True, **('background',))(stop_run)

import pathlib as _pathlib
from shlex import quote as _q, split as _split
from bearhub.core import fofn as _fofn
_ASSEMBLY_MODES = [
    'Illumina PE (Shovill)',
    'Illumina PE (Unicycler)',
    'Illumina SE (Shovill-SE)',
    'ONT (Dragonflye)',
    'Hybrid (Unicycler --hybrid)',
    'Hybrid (Dragonflye --short_polish)']
_MODE_IMPLIED = {
    'Illumina PE (Shovill)': (False, None),
    'Illumina PE (Unicycler)': (True, None),
    'Illumina SE (Shovill-SE)': (False, None),
    'ONT (Dragonflye)': (False, None),
    'Hybrid (Unicycler --hybrid)': (False, '--hybrid'),
    'Hybrid (Dragonflye --short_polish)': (False, '--short_polish') }
# WARNING: Decompyle incomplete
