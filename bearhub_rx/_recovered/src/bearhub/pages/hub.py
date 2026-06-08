# Source Generated with Decompyle++
# File: hub.cpython-311.pyc (Python 3.11)

'''Hub landing page — entry cards for each tool.'''
from __future__ import annotations
import reflex as rx
from bearhub.components.shell import shell
from bearhub.data.catalog import BACTOPIA_VERSION, TOOLS
CARDS = [
    ('Bactopia', '/bactopia', 'dna', 'Run the main pipeline: QC, assembly, annotation and typing from raw reads.'),
    ('Bactopia Tools', '/tools', 'wrench', f'''Run any of {len(TOOLS)} official --wf tools over already-processed samples.'''),
    ('MERLIN', '/merlin', 'wand-sparkles', 'Species-specific typing workflows, selected automatically per genus.'),
    ('Status', '/status', 'activity', 'Check Bactopia, Nextflow, Java and Docker versions.')]

def _card(title = None, href = None, icon = None, desc = ('title', 'str', 'href', 'str', 'icon', 'str', 'desc', 'str', 'return', 'rx.Component')):
    return rx.link(rx.card(rx.hstack(rx.box(rx.icon(icon, size = 26, color = 'white'), padding = '12px', border_radius = '12px', background = 'linear-gradient(135deg,#0f766e,#134e4a)'), rx.vstack(rx.heading(title, size = '4'), rx.text(desc, size = '2', color = 'var(--gray-10)'), spacing = '1', align = 'start'), spacing = '4', align = 'center', width = '100%'), width = '100%', _hover = {
        'border_color': 'var(--teal-8)' }), href = href, underline = 'none', width = '100%')


def hub_page():
    pass
# WARNING: Decompyle incomplete

