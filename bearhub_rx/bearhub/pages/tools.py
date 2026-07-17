"""Bactopia Tools — guided wizard over all official --wf tools."""
from __future__ import annotations

import reflex as rx

from bearhub.components.shell import shell
from bearhub.components import wizard as wz
from bearhub.components import help as helpmod
from bearhub.data import catalog
from bearhub.data.catalog import CATEGORY_ORDER, FIELD_SPECS, TOOLS, tools_in_category
from bearhub.state import ToolsState

STEPS = ["Data", "Tools", "Parameters", "Run"]

_HELP_KEY = {"amrfinderplus": "amrfinder"}


def _field(field: dict) -> rx.Component:
    key   = field["key"]
    kind  = field["kind"]
    label = field["label"]
    if kind == "bool":
        return rx.checkbox(
            label,
            checked=ToolsState.flags[key],
            color_scheme="indigo",
            on_change=lambda v: ToolsState.set_flag(key, v),
        )
    if kind == "select":
        return wz.labeled(
            label,
            rx.select(
                field.get("options", []),
                value=ToolsState.opts[key],
                size="2",
                on_change=lambda v: ToolsState.set_opt(key, v),
            ),
        )
    if kind == "path":
        return wz.labeled(
            label,
            rx.hstack(
                rx.input(
                    value=ToolsState.opts[key],
                    type="text",
                    size="2",
                    width="300px",
                    placeholder=field.get("help", "/absolute/path"),
                    on_change=lambda v: ToolsState.set_opt(key, v),
                ),
                rx.button(
                    rx.icon("folder-open", size=15), "Browse",
                    on_click=lambda: ToolsState.open_picker_for(f"opt:{key}"),
                    variant="soft", color_scheme="gray", size="2",
                ),
                spacing="2", align="center",
            ),
        )
    typ = "number" if kind in ("int", "float") else "text"
    return wz.labeled(
        label,
        rx.input(
            value=ToolsState.opts[key],
            type=typ,
            size="2",
            width="160px",
            placeholder=field.get("help", ""),
            on_change=lambda v: ToolsState.set_opt(key, v),
        ),
    )


def _detailed_panel(tool: dict) -> rx.Component:
    tid = tool["id"]
    fields = FIELD_SPECS.get(tid, [])
    return rx.cond(
        ToolsState.picks[tid],
        rx.card(
            rx.vstack(
                helpmod.section(
                    tool["label"],
                    _HELP_KEY.get(tid, tid),
                    size="3",
                ),
                rx.flex(
                    *[_field(f) for f in fields],
                    wrap="wrap",
                    spacing="4",
                    align="end",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            width="100%",
        ),
    )


def _tool_card(tool: dict) -> rx.Component:
    tid     = tool["id"]
    checked = ToolsState.picks[tid]
    head: list[rx.Component] = [
        rx.text(tool["label"], weight="bold", size="2"),
    ]
    if tool["detailed"]:
        head.append(
            rx.badge("options", size="1", color_scheme="indigo", variant="soft")
        )
    return rx.card(
        rx.hstack(
            rx.checkbox(
                checked=checked,
                color_scheme="indigo",
                size="3",
                style={"pointerEvents": "none"},
            ),
            rx.vstack(
                rx.hstack(*head, spacing="2", align="center"),
                rx.text(tool["desc"], size="2", color="var(--gray-10)"),
                spacing="0",
                align="start",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        on_click=ToolsState.toggle(tid),
        cursor="pointer",
        style={
            "borderColor": rx.cond(checked, "var(--accent-8)", "var(--gray-5)"),
            "background":  rx.cond(checked, "var(--accent-2)", "transparent"),
        },
        width="100%",
    )


def _category_block(cat: str) -> rx.Component:
    items = tools_in_category(cat)
    if not items:
        return rx.fragment()
    return rx.vstack(
        rx.hstack(
            rx.heading(cat, size="3", color="var(--accent-11)"),
            rx.badge(
                str(len(items)), color_scheme="gray",
                variant="soft",
            ),
            spacing="2", align="center",
        ),
        rx.grid(
            *[_tool_card(t) for t in items],
            columns="2",
            spacing="3",
            width="100%",
        ),
        spacing="3", align="start", width="100%",
    )


def _step_data() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Browse to a Bactopia output directory; samples come from its subfolders.",
            size="2", color="var(--gray-10)",
        ),
        wz.dir_field(ToolsState),
        wz.samples_field(ToolsState),
        wz.nav_buttons(ToolsState.prev_step, ToolsState.next_step, first=True),
        spacing="6", width="100%", align="start",
    )


def _step_tools() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                "Pick one or more tools — each runs as its own --wf, sequentially.",
                size="2", color="var(--gray-10)",
            ),
            rx.spacer(),
            rx.badge(
                ToolsState.n_picked.to_string() + " selected",
                color_scheme="indigo",
                size="2",
            ),
            width="100%", align="center",
        ),
        *[_category_block(cat) for cat in CATEGORY_ORDER],
        wz.nav_buttons(ToolsState.prev_step, ToolsState.next_step),
        spacing="6", width="100%", align="start",
    )


def _step_params() -> rx.Component:
    return rx.vstack(
        rx.text(
            "General Nextflow settings, then per-tool options for the tools you picked.",
            size="2", color="var(--gray-10)",
        ),
        wz.general_params(ToolsState),
        wz.labeled(
            "Extras (raw line)",
            rx.input(
                value=ToolsState.extra,
                on_change=ToolsState.set_extra,
                width="100%",
                size="2",
                placeholder="-with-report report.html",
            ),
            width="100%",
        ),
        rx.cond(
            ToolsState.picked_detailed.length() > 0,
            rx.vstack(
                *[_detailed_panel(t) for t in TOOLS if t["detailed"]],
                spacing="4",
                width="100%",
            ),
        ),
        wz.dir_picker(ToolsState),
        wz.nav_buttons(
            ToolsState.prev_step, ToolsState.next_step,
            next_label="Review & run",
        ),
        spacing="6", width="100%", align="start",
    )


def _step_run() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.hstack(
                rx.text("Tools", size="1", color="var(--gray-10)"),
                rx.foreach(
                    ToolsState.picked_ids,
                    lambda t: rx.badge(t, color_scheme="indigo"),
                ),
                wrap="wrap", spacing="2", align="center",
            ),
            rx.text(
                ToolsState.n_selected.to_string(),
                " samples · profile ",
                ToolsState.profile,
                size="2", color="var(--gray-11)", margin_top="6px",
            ),
            width="100%",
            style={"background": "var(--accent-2)", "borderColor": "var(--accent-6)"},
        ),
        wz.docker_banner(ToolsState),
        rx.hstack(
            rx.heading("Command preview", size="3"),
            rx.spacer(),
            wz.copy_button(ToolsState.preview, "Copy command"),
            width="100%", align="center",
        ),
        rx.code_block(ToolsState.preview, language="bash",
                      width="100%", wrap_long_lines=True),
        wz.run_panel(ToolsState, can_run=ToolsState.ready),
        wz.merged_panel(ToolsState),
        wz.nav_buttons(
            ToolsState.prev_step, ToolsState.next_step,
            next_label="Back", next_handler=ToolsState.prev_step,
        ),
        spacing="6", width="100%", align="start",
    )


def tools_page() -> rx.Component:
    return shell(
        wz.hero("wrench", "Bactopia Tools",
                "Run official --wf workflows over already-processed samples."),
        wz.step_indicator(STEPS, ToolsState.step, ToolsState.goto,
                          help_keys=["step_data", "step_tools", "step_params", "step_run"]),
        rx.divider(),
        rx.match(
            ToolsState.step,
            (0, _step_data()),
            (1, _step_tools()),
            (2, _step_params()),
            (3, _step_run()),
            _step_data(),
        ),
        active="/tools",
    )
