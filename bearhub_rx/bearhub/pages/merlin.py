"""MERLIN — species-specific typing workflows (guided wizard)."""
from __future__ import annotations

import reflex as rx

from bearhub.components.shell import shell
from bearhub.components import wizard as wz
from bearhub.components import help as helpmod
from bearhub.data.catalog import MERLIN_SPECIES
from bearhub.state import MerlinState

STEPS = ["Data", "Species tools", "Parameters", "Run"]


def _species_chip(label: str, wf: str) -> rx.Component:
    checked = MerlinState.picks[wf]
    return rx.card(
        rx.hstack(
            rx.checkbox(
                checked=checked,
                color_scheme="teal",
                size="2",
                style={"pointerEvents": "none"},
            ),
            rx.text(label, size="2", weight="medium"),
            rx.code(wf, size="1"),
            spacing="2",
            align="center",
        ),
        on_click=MerlinState.toggle(wf),
        cursor="pointer",
        padding="8px 12px",
        style={
            "borderColor": rx.cond(checked, "var(--teal-8)", "var(--gray-5)"),
            "background":  rx.cond(checked, "var(--teal-2)", "transparent"),
        },
    )


def _genus_block(genus: str, tools: list) -> rx.Component:
    return rx.vstack(
        rx.heading(genus, size="3", color="var(--teal-11)"),
        rx.flex(
            *[_species_chip(label, wf) for label, wf in tools],
            wrap="wrap",
            spacing="2",
        ),
        spacing="2",
        align="start",
        width="100%",
    )


def _step_data() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Browse to a Bactopia output directory; samples come from its subfolders.",
            size="2", color="var(--gray-10)",
        ),
        wz.dir_field(MerlinState),
        wz.samples_field(MerlinState),
        wz.nav_buttons(MerlinState.prev_step, MerlinState.next_step, first=True),
        spacing="6", width="100%", align="start",
    )


def _step_tools() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            helpmod.section("Species-specific tools", "merlin", size="4"),
            rx.spacer(),
            rx.badge(
                MerlinState.n_picked.to_string() + " selected",
                color_scheme="teal",
                size="2",
            ),
            width="100%", align="center",
        ),
        rx.text(
            "Tick the workflows to run. Each runs as its own --wf.",
            size="2", color="var(--gray-10)",
        ),
        *[_genus_block(genus, tools) for genus, tools in MERLIN_SPECIES],
        wz.nav_buttons(MerlinState.prev_step, MerlinState.next_step),
        spacing="6", width="100%", align="start",
    )


def _step_params() -> rx.Component:
    return rx.vstack(
        rx.text(
            "General Nextflow settings applied to every selected workflow.",
            size="2", color="var(--gray-10)",
        ),
        wz.general_params(MerlinState),
        wz.labeled(
            "Extras (raw line)",
            rx.input(
                value=MerlinState.extra,
                on_change=MerlinState.set_extra,
                width="100%",
                size="2",
            ),
            width="100%",
        ),
        wz.nav_buttons(
            MerlinState.prev_step, MerlinState.next_step,
            next_label="Review & run",
        ),
        spacing="6", width="100%", align="start",
    )


def _step_run() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.hstack(
                rx.text("Workflows", size="1", color="var(--gray-10)"),
                rx.foreach(
                    MerlinState.picked_ids,
                    lambda t: rx.badge(t, color_scheme="teal"),
                ),
                wrap="wrap", spacing="2", align="center",
            ),
            rx.text(
                MerlinState.n_selected.to_string(),
                " samples · profile ",
                MerlinState.profile,
                size="2", color="var(--gray-11)", margin_top="6px",
            ),
            width="100%",
            style={"background": "var(--teal-2)", "borderColor": "var(--teal-6)"},
        ),
        rx.heading("Command preview", size="3"),
        rx.code_block(MerlinState.preview, language="bash",
                      width="100%", wrap_long_lines=True),
        wz.run_panel(MerlinState),
        wz.merged_panel(MerlinState),
        wz.nav_buttons(
            MerlinState.prev_step, MerlinState.next_step,
            next_label="Back", next_handler=MerlinState.prev_step,
        ),
        spacing="6", width="100%", align="start",
    )


def merlin_page() -> rx.Component:
    return shell(
        wz.hero("wand-sparkles", "MERLIN",
                "Species-specific typing workflows for completed samples."),
        wz.step_indicator(STEPS, MerlinState.step, MerlinState.goto),
        rx.divider(),
        rx.match(
            MerlinState.step,
            (0, _step_data()),
            (1, _step_tools()),
            (2, _step_params()),
            (3, _step_run()),
            _step_data(),
        ),
        active="/merlin",
    )
