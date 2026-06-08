# Source Generated with Decompyle++
# File: help.cpython-310.pyc (Python 3.10)

'''Help popover ("?") with colored text + section headers (data/help_texts).'''
from __future__ import annotations
import re
import reflex as rx
from bearhub.data.help_texts import HELP
_FLAG = re.compile('(--?[A-Za-z][\\w-]*)')

def _inline(text = None):
    '''Color flag-like tokens (--scheme, -M, …) inside a line.'''
    text = text.replace('**', '').replace('`', '')
    spans = []
    last = 0
    for m in _FLAG.finditer(text):
        if m.start() > last:
            spans.append(rx.text.span(text[last:m.start()]))
        spans.append(rx.text.span(m.group(1), {
            'color': 'var(--teal-11)',
            'fontFamily': 'monospace',
            'fontWeight': '600' }, **('style',)))
        last = m.end()
    if last < len(text):
        spans.append(rx.text.span(text[last:]))
    if not spans:
        pass
    return [
        rx.text.span(text)]


def render_help(md = None):
    '''Render our help markdown as colored Reflex text (no react-markdown).'''
    blocks = []
# WARNING: Decompyle incomplete


def help_button(key = None):
    md = HELP.get(key)
    if not md:
        return rx.fragment()
    return None.popover.root(rx.popover.trigger(rx.icon('circle-help', 15, 'var(--teal-9)', {
        'cursor': 'pointer' }, **('size', 'color', 'style'))), rx.popover.content(rx.scroll_area(rx.box(render_help(md), '10px', **('padding_right',)), 'vertical', {
        'maxHeight': '360px' }, **('scrollbars', 'style')), '460px', 'right', 'start', **('width', 'side', 'align')))


def section(title = None, key = None, size = None):
    '''A heading with an optional inline help button.'''
    return rx.hstack(rx.heading(title, size, **('size',)), help_button(key) if key else rx.fragment(), '2', 'center', **('spacing', 'align'))


def field_label(label = None, key = None):
    '''Small field caption with an optional help button.'''
    return rx.hstack(rx.text(label, '1', 'var(--gray-10)', **('size', 'color')), help_button(key) if key else rx.fragment(), '1', 'center', **('spacing', 'align'))

