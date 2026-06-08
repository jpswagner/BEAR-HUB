# Source Generated with Decompyle++
# File: tools.cpython-310.pyc (Python 3.10)

'''Bactopia Tools — guided wizard over all official --wf tools.'''
from __future__ import annotations
import reflex as rx
from bearhub.components.shell import shell
from bearhub.components import wizard as wz
from bearhub.components import help as helpmod
from bearhub.data import catalog
from bearhub.data.catalog import CATEGORY_ORDER, FIELD_SPECS, TOOLS, tools_in_category
from bearhub.state import ToolsState
STEPS = [
    'Data',
    'Tools',
    'Parameters',
    'Run']

def _tool_card(tool = None):
    tid = tool['id']
    checked = ToolsState.picks[tid]
    head = [
        rx.text(tool['label'], 'bold', '2', **('weight', 'size'))]
    if tool['detailed']:
        head.append(rx.badge('options', '1', 'teal', 'soft', **('size', 'color_scheme', 'variant')))
# WARNING: Decompyle incomplete


def _category_block(cat = None):
    items = tools_in_category(cat)
# WARNING: Decompyle incomplete


def _field(field = None):
    key = field['key']
    kind = field['kind']
    label = field['label']
    if kind == 'bool':
        return None(None, None, None, (lambda v = None: ToolsState.set_flag(key, v)), **('checked', 'color_scheme', 'on_change'))
    if None == 'select':
        return None(None, None(None, None, None, (lambda v = None: ToolsState.set_opt(key, v)), **('value', 'size', 'on_change')))
    typ = 'number' if None in ('int', 'float') else 'text'
    return None(None, None(None, None, None, None, None, (lambda v = wz.labeled: ToolsState.set_opt(key, v)), **('value', 'type', 'size', 'width', 'placeholder', 'on_change')))

_HELP_KEY = {
    'amrfinderplus': 'amrfinder' }

def _detailed_panel(tool = None):
    tid = tool['id']
# WARNING: Decompyle incomplete


def _step_data():
    return rx.vstack(rx.text('Browse to a Bactopia output directory; samples come from its subfolders.', '2', 'var(--gray-10)', **('size', 'color')), wz.dir_field(ToolsState), wz.samples_field(ToolsState), wz.nav_buttons(ToolsState.prev_step, ToolsState.next_step, True, **('first',)), '6', '100%', 'start', **('spacing', 'width', 'align'))


def _step_tools():
    pass
# WARNING: Decompyle incomplete


def _step_params():
    pass
# WARNING: Decompyle incomplete


def _step_run():
    return rx.vstack(rx.card(rx.hstack(rx.text('Tools', '1', 'var(--gray-10)', **('size', 'color')), rx.foreach(ToolsState.picked_ids, (lambda t: rx.badge(t, 'teal', **('color_scheme',)))), 'wrap', '2', 'center', **('wrap', 'spacing', 'align')), rx.text(f'''{ToolsState.n_selected} samples · profile {ToolsState.profile}''', '2', 'var(--gray-11)', '6px', **('size', 'color', 'margin_top')), '100%', {
        'background': 'var(--teal-2)',
        'borderColor': 'var(--teal-6)' }, **('width', 'style')), rx.heading('Command preview', '3', **('size',)), rx.code_block(ToolsState.preview, 'bash', '100%', True, **('language', 'width', 'wrap_long_lines')), wz.run_panel(ToolsState), wz.merged_panel(ToolsState), wz.nav_buttons(ToolsState.prev_step, ToolsState.next_step, 'Back', ToolsState.prev_step, **('next_label', 'next_handler')), '6', '100%', 'start', **('spacing', 'width', 'align'))


def tools_page():
    return shell(wz.hero('wrench', 'Bactopia Tools', 'Run official --wf workflows over already-processed samples.'), wz.step_indicator(STEPS, ToolsState.step, ToolsState.goto), rx.divider(), rx.match(ToolsState.step, (0, _step_data()), (1, _step_tools()), (2, _step_params()), (3, _step_run()), _step_data()), '/tools', **('active',))

