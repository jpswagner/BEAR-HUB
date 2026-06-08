# Source Generated with Decompyle++
# File: wizard.cpython-310.pyc (Python 3.10)

'''Reusable wizard chrome: hero banner, step indicator, run panel, dir picker.'''
from __future__ import annotations
import os
import reflex as rx
from bearhub.components.help import section as help_section
if not os.cpu_count():
    pass
_MAX_CPUS = min(64, 128)

def hero(icon = None, title = None, subtitle = None):
    return rx.box(rx.hstack(rx.icon(icon, 32, 'white', **('size', 'color')), rx.vstack(rx.heading(title, '6', 'white', **('size', 'color')), rx.text(subtitle, '2', 'white', '0.85', **('size', 'color', 'opacity')), '0', 'start', **('spacing', 'align')), '4', 'center', **('spacing', 'align')), '20px 24px', '16px', '100%', 'linear-gradient(135deg, #0f766e 0%, #115e59 55%, #134e4a 100%)', '0 8px 24px rgba(15,118,110,.25)', **('padding', 'border_radius', 'width', 'background', 'box_shadow'))


def step_indicator(steps = None, current = None, goto = None):
    '''`current` is a state int Var; `goto` is an event handler taking the index.'''
    nodes = []
    for idx, label in enumerate(steps):
        active = current == idx
        done = current > idx
        circle = rx.box(rx.cond(done, rx.icon('check', 16, 'white', **('size', 'color')), rx.text(idx + 1, '2', 'bold', 'white', **('size', 'weight', 'color'))), '30px', '30px', '9999px', 'flex', 'center', 'center', rx.cond(active | done, 'var(--teal-9)', 'var(--gray-6)'), rx.cond(active, '0 0 0 4px var(--teal-4)', 'none'), 'all .15s ease', **('width', 'height', 'border_radius', 'display', 'align_items', 'justify_content', 'background', 'box_shadow', 'transition'))
        nodes.append(rx.hstack(circle, rx.text(label, '2', rx.cond(active, 'bold', 'regular'), rx.cond(active | done, 'var(--teal-11)', 'var(--gray-10)'), **('size', 'weight', 'color')), '2', 'center', 'pointer', goto(idx), **('spacing', 'align', 'cursor', 'on_click')))
        if idx < len(steps) - 1:
            nodes.append(rx.box('32px', '2px', '2px', rx.cond(done, 'var(--teal-9)', 'var(--gray-6)'), **('width', 'height', 'border_radius', 'background')))
# WARNING: Decompyle incomplete


def nav_buttons(prev_step = None, next_step = None, *, first, next_label, next_icon, next_handler):
    btns = []
    if not first:
        btns.append(rx.button('Back', prev_step, 'soft', 'gray', '3', **('on_click', 'variant', 'color_scheme', 'size')))
    if not next_handler:
        pass
    btns.append(rx.button(next_label, rx.icon(next_icon, 16, **('size',)), next_step, 'teal', '3', **('on_click', 'color_scheme', 'size')))
# WARNING: Decompyle incomplete


def labeled(label = None, *, width, *children):
    pass
# WARNING: Decompyle incomplete


def run_panel(S = None):
    '''Run/Stop buttons, status badge, and the live log. `S` is a page state.'''
    return rx.vstack(rx.hstack(rx.button(rx.icon('play', 18, **('size',)), 'Run', S.run, 'teal', '4', S.running, S.running, **('on_click', 'color_scheme', 'size', 'disabled', 'loading')), rx.button(rx.icon('square', 16, **('size',)), 'Stop', S.stop_run, 'red', 'soft', '4', ~(S.running), **('on_click', 'color_scheme', 'variant', 'size', 'disabled')), rx.cond(S.status != 'idle', rx.badge(S.status_label, S.status_color, '2', **('color_scheme', 'size'))), '5', 'center', **('spacing', 'align')), rx.box(rx.code_block(S.log_text, 'bash', '100%', True, **('language', 'width', 'wrap_long_lines')), rx.cond(S.log.length() == 0, rx.text('Output will stream here when you run.', '1', 'var(--gray-9)', '8px', **('size', 'color', 'padding'))), '100%', '320px', 'auto', '1px solid var(--gray-5)', '8px', 'var(--gray-2)', **('width', 'height', 'overflow', 'border', 'border_radius', 'background')), '5', '100%', 'start', **('spacing', 'width', 'align'))


def dir_picker(S = None):
    '''Directory browser dialog bound to a WizardMixin-derived state `S`.'''
    return None(None(None, None, None, None(None(None(rx.dialog.root, (lambda d = rx.dialog.content: rx.hstack(rx.icon('folder', 'var(--amber-9)', 18, **('color', 'size')), rx.text(d, 'monospace', '2', **('font_family', 'size')), '2', 'center', '100%', '6px 8px', '6px', 'pointer', S.picker_enter(d), {
'background': 'var(--gray-3)' }, **('spacing', 'align', 'width', 'padding', 'border_radius', 'cursor', 'on_click', '_hover')))), '0', '100%', **('spacing', 'width')), 'auto', 'vertical', '260px', '1px solid var(--gray-5)', '8px', '4px', **('type', 'scrollbars', 'height', 'border', 'border_radius', 'padding')), rx.hstack(rx.dialog.close(rx.button('Cancel', 'soft', 'gray', **('variant', 'color_scheme'))), rx.button('Select this folder', rx.icon('check', 16, **('size',)), S.picker_select, 'teal', **('on_click', 'color_scheme')), 'end', '2', '12px', '100%', **('justify', 'spacing', 'margin_top', 'width')), '540px', **('max_width',)), S.picker_open, S.set_picker_open, **('open', 'on_open_change'))


def dir_input(S = None, target = None, value = None, with_rescan = ('outdir', None, True)):
    '''Read-only directory input + Browse (+ optional Rescan). No dialog.'''
    val = S.outdir if value is None else value
    btns = [
        rx.input(val, True, 'monospace', '100%', '3', **('value', 'read_only', 'font_family', 'width', 'size')),
        rx.button(rx.icon('folder-open', 16, **('size',)), 'Browse…', S.open_picker_for(target), 'teal', '3', **('on_click', 'color_scheme', 'size'))]
    if with_rescan:
        btns.append(rx.button(rx.icon('refresh-cw', 16, **('size',)), S.scan, 'soft', '3', **('on_click', 'variant', 'size')))
# WARNING: Decompyle incomplete


def dir_field(S = None):
    '''Output-dir input + the picker dialog (single-picker pages).'''
    return rx.vstack(dir_input(S, 'outdir'), dir_picker(S), '100%', **('width',))


def samples_field(S = None):
    '''Discovered samples as toggle chips + select-all/clear.'''
    return None(None, None(None(None(None, (lambda s = None: rx.badge(s, rx.cond(S.selected.contains(s), 'teal', 'gray'), rx.cond(S.selected.contains(s), 'solid', 'soft'), '2', 'pointer', S.toggle_sample(s), **('color_scheme', 'variant', 'size', 'cursor', 'on_click')))), 'wrap', '3', **('wrap', 'spacing')), 'auto', 'vertical', '170px', '100%', **('type', 'scrollbars', 'max_height', 'width')), '3', '100%', 'start', **('spacing', 'width', 'align'))


def merged_panel(S = None):
    '''Lists merged-results TSVs from the latest bactopia-runs (with a Refresh).'''
    return rx.card(rx.hstack(help_section('merged-results (latest run)', 'merged', '3', **('size',)), rx.spacer(), rx.button(rx.icon('refresh-cw', 14, **('size',)), 'Refresh', S.refresh_merged, 'soft', '1', **('on_click', 'variant', 'size')), '100%', 'center', **('width', 'align')), rx.cond(S.merged.length() > 0, rx.vstack(rx.foreach(S.merged, (lambda f: rx.hstack(rx.icon('file-text', 16, 'var(--teal-9)', **('size', 'color')), rx.text(f, 'monospace', '2', **('font_family', 'size')), '2', 'center', **('spacing', 'align')))), rx.text(S.merged_dir, '1', 'var(--gray-9)', 'monospace', **('size', 'color', 'font_family')), '1', 'start', '100%', **('spacing', 'align', 'width')), rx.text('No merged-results yet. Run a workflow, then Refresh.', '1', 'var(--gray-9)', **('size', 'color'))), '100%', **('width',))


def _slider_field(label, value_var = None, handler = None, lo = None, hi = ('',), suffix = ('label', 'str', 'lo', 'int', 'hi', 'int', 'suffix', 'str', 'return', 'rx.Component')):
    return rx.vstack(rx.hstack(rx.text(label, '1', 'var(--gray-10)', **('size', 'color')), rx.badge(rx.cond(value_var == 0, '∞', value_var.to_string() + suffix), 'teal', 'soft', **('color_scheme', 'variant')), '2', 'center', **('spacing', 'align')), rx.slider([
        value_var], lo, hi, 1, handler, 'teal', '240px', **('value', 'min', 'max', 'step', 'on_change', 'color_scheme', 'width')), '2', 'start', '240px', **('spacing', 'align', 'width'))


def general_params(S = None):
    return rx.flex(labeled('-profile', rx.select([
        'docker',
        'singularity',
        'standard'], S.profile, S.set_profile, '3', **('value', 'on_change', 'size'))), _slider_field('--max_cpus (0 = ∞)', S.threads, S.set_threads, 0, _MAX_CPUS), _slider_field('--max_memory (0 = ∞)', S.memory, S.set_memory, 0, 256, ' GB'), labeled('-resume', rx.switch(S.resume, S.set_resume, 'teal', **('checked', 'on_change', 'color_scheme'))), 'wrap', '5', 'end', '100%', **('wrap', 'spacing', 'align', 'width'))

