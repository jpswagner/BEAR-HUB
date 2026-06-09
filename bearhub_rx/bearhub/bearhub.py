"""BEAR-HUB — Reflex application entry point."""
from __future__ import annotations

import reflex as rx

from bearhub.core import system

system.bootstrap_env()

from bearhub.pages.bactopia import bactopia_page
from bearhub.pages.hub import hub_page
from bearhub.pages.merlin import merlin_page
from bearhub.pages.runs import runs_page
from bearhub.pages.status import status_page
from bearhub.pages.tools import tools_page
from bearhub.state import BactopiaState, MerlinState, RunsState, StatusState, ToolsState

app = rx.App(
    theme=rx.theme(accent_color="teal", gray_color="slate", radius="large", appearance="light")
)
app.add_page(hub_page, route="/", title="BEAR-HUB")
app.add_page(
    bactopia_page,
    route="/bactopia",
    title="Bactopia — BEAR-HUB",
    on_load=BactopiaState.init_outdir,
)
app.add_page(
    tools_page, route="/tools", title="Bactopia Tools — BEAR-HUB", on_load=ToolsState.init_outdir
)
app.add_page(
    merlin_page, route="/merlin", title="MERLIN — BEAR-HUB", on_load=MerlinState.init_outdir
)
app.add_page(runs_page, route="/runs", title="Runs — BEAR-HUB", on_load=RunsState.load)
app.add_page(status_page, route="/status", title="Status — BEAR-HUB", on_load=StatusState.load)
