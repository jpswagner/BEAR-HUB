# Source Generated with Decompyle++
# File: shell.cpython-311.pyc (Python 3.11)

'''App shell: fixed top bar + persistent left sidebar navigation.'''
from __future__ import annotations
import reflex as rx
from bearhub.data.catalog import BACTOPIA_VERSION
NAV = [
    ('Hub', '/', 'house'),
    ('Bactopia', '/bactopia', 'dna'),
    ('Bactopia Tools', '/tools', 'wrench'),
    ('MERLIN', '/merlin', 'wand-sparkles'),
    ('Status', '/status', 'activity')]

def _nav_item(label = None, href = None, icon = None, active = ('label', 'str', 'href', 'str', 'icon', 'str', 'active', 'str', 'return', 'rx.Component')):
    is_active = href == active
    return rx.link(rx.hstack(rx.icon(icon, size = 18), rx.text(label, size = '2', weight = 'bold' if is_active else 'regular'), spacing = '3', align = 'center', width = '100%', padding = '9px 12px', border_radius = '8px', background = 'var(--teal-4)' if is_active else 'transparent', color = 'var(--teal-11)' if is_active else 'var(--gray-11)', _hover = {
        'background': 'var(--teal-3)' if is_active else 'var(--gray-3)' }), href = href, underline = 'none', width = '100%')


def _sidebar(active = None):
    pass
# WARNING: Decompyle incomplete


def _topbar():
    return rx.hstack(rx.hstack(rx.text('🐻', font_size = '22px'), rx.heading('BEAR-HUB', size = '4'), rx.badge('Reflex', color_scheme = 'teal', variant = 'surface', size = '1'), spacing = '2', align = 'center'), rx.spacer(), rx.color_mode.button(), align = 'center', width = '100%', height = '56px', padding = '0 20px', border_bottom = '1px solid var(--gray-4)', position = 'sticky', top = '0', background = 'var(--color-background)', z_index = '20')


def shell(*, active, *content):
    pass
# WARNING: Decompyle incomplete

