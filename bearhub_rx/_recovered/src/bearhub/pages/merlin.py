# Source Generated with Decompyle++
# File: merlin.cpython-310.pyc (Python 3.10)

'''MERLIN — species-specific typing workflows (guided wizard).'''
from __future__ import annotations
import reflex as rx
from bearhub.components.shell import shell
from bearhub.components import wizard as wz
from bearhub.components import help as helpmod
from bearhub.data.catalog import MERLIN_SPECIES
from bearhub.state import MerlinState
STEPS = [
    'Data',
    'Species tools',
    'Parameters',
    'Run']

def _species_chip(label = None, wf = None):
    checked = MerlinState.picks[wf]
    return rx.card(rx.hstack(rx.checkbox(checked, 'teal', '2', {
        'pointerEvents': 'none' }, **('checked', 'color_scheme', 'size', 'style')), rx.text(label, '2', 'medium', **('size', 'weight')), rx.code(wf, '1', **('size',)), '2', 'center', **('spacing', 'align')), MerlinState.toggle(wf), 'pointer', '8px 12px', {
        'borderColor': rx.cond(checked, 'var(--teal-8)', 'var(--gray-5)'),
        'background': rx.cond(checked, 'var(--teal-2)', 'transparent') }, **('on_click', 'cursor', 'padding', 'style'))


def _genus_block(genus = None, tools = None):
    pass
# WARNING: Decompyle incomplete


def _step_data():
    return rx.vstack(rx.text('Browse to a Bactopia output directory; samples come from its subfolders.', '2', 'var(--gray-10)', **('size', 'color')), wz.dir_field(MerlinState), wz.samples_field(MerlinState), wz.nav_buttons(MerlinState.prev_step, MerlinState.next_step, True, **('first',)), '6', '100%', 'start', **('spacing', 'width', 'align'))


def _step_tools():
    pass
# WARNING: Decompyle incomplete


def _step_params():
    return rx.vstack(rx.text('General Nextflow settings applied to every selected workflow.', '2', 'var(--gray-10)', **('size', 'color')), wz.general_params(MerlinState), wz.labeled('Extras (raw line)', rx.input(MerlinState.extra, MerlinState.set_extra, '100%', '2', **('value', 'on_change', 'width', 'size')), '100%', **('width',)), wz.nav_buttons(MerlinState.prev_step, MerlinState.next_step, 'Review & run', **('next_label',)), '6', '100%', 'start', **('spacing', 'width', 'align'))


def _step_run():
    return rx.vstack(rx.card(rx.hstack(rx.text('Workflows', '1', 'var(--gray-10)', **('size', 'color')), rx.foreach(MerlinState.picked_ids, (lambda t: rx.badge(t, 'teal', **('color_scheme',)))), 'wrap', '2', 'center', **('wrap', 'spacing', 'align')), rx.text(f'''{MerlinState.n_selected} samples · profile {MerlinState.profile}''', '2', 'var(--gray-11)', '6px', **('size', 'color', 'margin_top')), '100%', {
        'background': 'var(--teal-2)',
        'borderColor': 'var(--teal-6)' }, **('width', 'style')), rx.heading('Command preview', '3', **('size',)), rx.code_block(MerlinState.preview, 'bash', '100%', True, **('language', 'width', 'wrap_long_lines')), wz.run_panel(MerlinState), wz.merged_panel(MerlinState), wz.nav_buttons(MerlinState.prev_step, MerlinState.next_step, 'Back', MerlinState.prev_step, **('next_label', 'next_handler')), '6', '100%', 'start', **('spacing', 'width', 'align'))


def merlin_page():
    return shell(wz.hero('wand-sparkles', 'MERLIN', 'Species-specific typing workflows for completed samples.'), wz.step_indicator(STEPS, MerlinState.step, MerlinState.goto), rx.divider(), rx.match(MerlinState.step, (0, _step_data()), (1, _step_tools()), (2, _step_params()), (3, _step_run()), _step_data()), '/merlin', **('active',))

