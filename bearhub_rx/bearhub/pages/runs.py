"""Runs & History page — monitor active runs and browse past run records."""
from __future__ import annotations

import reflex as rx

from bearhub.components import wizard as wzmod
from bearhub.components.shell import shell
from bearhub.components.wizard import hero
from bearhub.state import RunsState


def _live_log_panel() -> rx.Component:
    """Live log of the selected run (tails its on-disk log; updates while active)."""
    return rx.vstack(
        rx.hstack(
            rx.text("Live log", size="2", weight="bold", color="var(--gray-11)"),
            rx.cond(
                RunsState.selected_active,
                rx.badge("● live", color_scheme="blue", size="1", variant="soft"),
            ),
            rx.spacer(),
            rx.cond(
                RunsState.selected_active,
                rx.button(
                    rx.icon("square", size=13), "Stop run",
                    on_click=RunsState.stop_selected,
                    color_scheme="red", variant="soft", size="1",
                ),
            ),
            wzmod.copy_button(RunsState.selected_log_text, "Copy log"),
            width="100%", align="center",
        ),
        rx.cond(
            RunsState.selected_log.length() > 0,
            wzmod.log_view(RunsState.selected_log_text, height="280px"),
            rx.text("No captured log for this run (older run, or log rotated).",
                    size="1", color="var(--gray-9)", padding="8px"),
        ),
        spacing="2", width="100%", align="start", margin_top="6px",
    )


def _run_row(r) -> rx.Component:
    """Row renderer for rx.foreach — `r` is a Reflex Var (dict)."""
    rid    = r["id"]
    status = r["status"]
    color  = r["color"]   # pre-computed in RunsState._enrich()
    is_sel = RunsState.selected_id == rid

    return rx.table.row(
        rx.table.cell(
            rx.badge(rid, color_scheme="gray", variant="outline", size="1"),
        ),
        rx.table.cell(
            rx.badge(status, color_scheme=color, size="1", variant="soft"),
        ),
        rx.table.cell(
            rx.text(r["page"], size="2"),
        ),
        rx.table.cell(
            rx.text(r["started_fmt"], size="2", color="var(--gray-10)"),
        ),
        rx.table.cell(
            rx.text(r["duration_fmt"], size="2", color="var(--gray-10)"),
        ),
        rx.table.cell(
            rx.text(r["samples_fmt"], size="2", color="var(--gray-10)"),
        ),
        rx.table.cell(
            rx.button(
                rx.icon("terminal", size=13),
                "cmd",
                on_click=RunsState.select(rid),
                size="1",
                variant="soft",
                color_scheme="indigo",
            ),
        ),
        style={
            "background": rx.cond(is_sel, "var(--accent-2)", "transparent"),
            "cursor": "pointer",
        },
        on_click=RunsState.select(rid),
    )


def _cmd_panel() -> rx.Component:
    return rx.cond(
        RunsState.selected_id != "",
        rx.card(
            rx.hstack(
                rx.text("Command", size="2", weight="bold", color="var(--gray-11)"),
                rx.badge(RunsState.selected_id, size="1", color_scheme="gray",
                         variant="outline"),
                rx.spacer(),
                wzmod.copy_button(RunsState.selected_cmd, "Copy"),
                rx.button(
                    rx.icon("x", size=14),
                    on_click=RunsState.clear_selected,
                    variant="ghost",
                    size="1",
                ),
                width="100%", align="center",
            ),
            rx.code_block(
                RunsState.selected_cmd,
                language="bash",
                width="100%",
                wrap_long_lines=True,
                font_size="12px",
            ),
            _live_log_panel(),
            width="100%",
        ),
    )


def _empty_state() -> rx.Component:
    return rx.vstack(
        rx.icon("history", size=40, color="var(--gray-6)"),
        rx.text("No runs yet.", size="3", color="var(--gray-10)"),
        rx.text(
            "Start a pipeline from Bactopia, Bactopia Tools or MERLIN.",
            size="2", color="var(--gray-9)",
        ),
        spacing="2",
        align="center",
        padding="40px",
        width="100%",
    )


def runs_page() -> rx.Component:
    return shell(
        hero("history", "Runs & History",
             "Monitor active runs and browse past pipeline executions."),
        rx.hstack(
            rx.hstack(
                rx.cond(
                    RunsState.active_count > 0,
                    rx.badge(
                        RunsState.active_count.to_string() + " running",
                        color_scheme="blue",
                        size="2",
                        variant="solid",
                    ),
                ),
                spacing="2",
                align="center",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("refresh-cw", size=14),
                "Refresh",
                on_click=[RunsState.refresh, RunsState.monitor],
                variant="soft",
                size="2",
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            RunsState.has_records,
            rx.vstack(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("ID"),
                            rx.table.column_header_cell("Status"),
                            rx.table.column_header_cell("Page"),
                            rx.table.column_header_cell("Started"),
                            rx.table.column_header_cell("Duration"),
                            rx.table.column_header_cell("Samples"),
                            rx.table.column_header_cell(""),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(RunsState.records, _run_row),
                    ),
                    width="100%",
                    size="1",
                ),
                _cmd_panel(),
                spacing="4",
                width="100%",
            ),
            _empty_state(),
        ),
        active="/runs",
    )
