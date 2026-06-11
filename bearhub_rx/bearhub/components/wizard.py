"""Reusable wizard chrome: hero banner, step indicator, run panel, dir picker."""
from __future__ import annotations

import os

import reflex as rx

from bearhub.components.help import section as help_section

_MAX_CPUS = min(os.cpu_count() or 4, 64)


def hero(icon: str, title: str, subtitle: str) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.icon(icon, size=32, color="white"),
            rx.vstack(
                rx.heading(title, size="6", color="white"),
                rx.text(subtitle, size="2", color="white", opacity="0.85"),
                spacing="0",
                align="start",
            ),
            spacing="4",
            align="center",
        ),
        padding="20px 24px",
        border_radius="16px",
        width="100%",
        background="linear-gradient(135deg, #0f766e 0%, #115e59 55%, #134e4a 100%)",
        box_shadow="0 8px 24px rgba(15,118,110,.25)",
    )


def step_indicator(steps: list[str], current, goto) -> rx.Component:
    """`current` is a state int Var; `goto` is an event handler taking the index."""
    nodes: list[rx.Component] = []
    for idx, label in enumerate(steps):
        active = current == idx
        done = current > idx
        circle = rx.box(
            rx.cond(
                done,
                rx.icon("check", size=16, color="white"),
                rx.text(idx + 1, size="2", weight="bold", color="white"),
            ),
            width="30px",
            height="30px",
            border_radius="9999px",
            display="flex",
            align_items="center",
            justify_content="center",
            background=rx.cond(active | done, "var(--teal-9)", "var(--gray-6)"),
            box_shadow=rx.cond(active, "0 0 0 4px var(--teal-4)", "none"),
            transition="all .15s ease",
        )
        nodes.append(
            rx.hstack(
                circle,
                rx.text(
                    label,
                    size="2",
                    weight=rx.cond(active, "bold", "regular"),
                    color=rx.cond(active | done, "var(--teal-11)", "var(--gray-10)"),
                ),
                spacing="2",
                align="center",
                cursor="pointer",
                on_click=goto(idx),
            )
        )
        if idx < len(steps) - 1:
            nodes.append(
                rx.box(
                    width="32px",
                    height="2px",
                    border_radius="2px",
                    background=rx.cond(done, "var(--teal-9)", "var(--gray-6)"),
                )
            )
    return rx.flex(*nodes, wrap="wrap", spacing="2", align="center", width="100%")


def nav_buttons(
    prev_step,
    next_step,
    *,
    first: bool = False,
    next_label: str = "Next",
    next_icon: str = "arrow-right",
    next_handler=None,
) -> rx.Component:
    btns: list[rx.Component] = []
    if not first:
        btns.append(
            rx.button("Back", on_click=prev_step, variant="soft",
                      color_scheme="gray", size="3")
        )
    handler = next_handler if next_handler else next_step
    btns.append(
        rx.button(
            next_label,
            rx.icon(next_icon, size=16),
            on_click=handler,
            color_scheme="teal",
            size="3",
        )
    )
    return rx.hstack(*btns, spacing="4", margin_top="20px")


def labeled(label: str, *children: rx.Component, width: str = "auto") -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="var(--gray-10)"),
        *children,
        spacing="1",
        align="start",
        width=width,
    )


def copy_button(text_var, label: str = "Copy", size: str = "1") -> rx.Component:
    """Small button that copies `text_var` (a state Var or str) to the clipboard."""
    return rx.button(
        rx.icon("copy", size=14), label,
        on_click=[rx.set_clipboard(text_var), rx.toast.info("Copied to clipboard")],
        variant="soft", color_scheme="gray", size=size,
    )


def log_view(log_text_var, empty_var=None, height: str = "320px") -> rx.Component:
    """Scrollable live-log box that auto-sticks to the newest line.

    The `column-reverse` flex trick keeps the scroll pinned to the bottom as
    new lines arrive (unless the user scrolls up), without any JS.
    """
    return rx.box(
        rx.code_block(log_text_var, language="bash", width="100%",
                      wrap_long_lines=True),
        rx.cond(
            (empty_var is not None) & (empty_var if empty_var is not None else False),
            rx.text("Output will stream here when you run.",
                    size="1", color="var(--gray-9)", padding="8px"),
        ),
        width="100%",
        height=height,
        overflow="auto",
        display="flex",
        flex_direction="column-reverse",
        border="1px solid var(--gray-5)",
        border_radius="8px",
        background="var(--gray-2)",
    )


def docker_banner(S) -> rx.Component:
    """Red callout shown when the Docker daemon isn't reachable (runs would fail)."""
    return rx.cond(
        ~S.docker_ok,
        rx.callout(
            "Docker daemon is not running. Bactopia runs with -profile docker and "
            "will fail until you start Docker (e.g. `sudo systemctl start docker`).",
            icon="triangle_alert", color_scheme="red", size="1",
        ),
    )


def run_panel(S, can_run=None) -> rx.Component:
    """Run/Stop buttons, status badge, and the live log. `S` is a page state.

    `can_run` (optional Var) gates the Run button so it's disabled until the
    page's prerequisites are met (FOFN built / tool & samples selected).
    """
    run_disabled = S.running if can_run is None else (S.running | ~can_run)
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.icon("play", size=18),
                "Run",
                on_click=S.run,
                color_scheme="teal",
                size="4",
                disabled=run_disabled,
                loading=S.running,
            ),
            rx.button(
                rx.icon("square", size=16),
                "Stop",
                on_click=S.stop_run,
                color_scheme="red",
                variant="soft",
                size="4",
                disabled=~S.running,
            ),
            rx.cond(
                S.status != "idle",
                rx.badge(S.status_label, color_scheme=S.status_color, size="2"),
            ),
            rx.spacer(),
            rx.cond(
                S.log.length() > 0,
                copy_button(S.log_text, "Copy log"),
            ),
            spacing="4",
            align="center",
            width="100%",
        ),
        log_view(S.log_text, S.log.length() == 0),
        spacing="5",
        width="100%",
        align="start",
    )


def dir_picker(S) -> rx.Component:
    """Directory browser dialog bound to a WizardMixin-derived state `S`."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Select a directory"),
            rx.text(
                S.picker_cur,
                font_family="monospace",
                size="1",
                color="var(--gray-10)",
                margin_bottom="8px",
            ),
            rx.vstack(
                rx.foreach(
                    S.picker_dirs,
                    lambda d: rx.hstack(
                        rx.icon("folder", color="var(--amber-9)", size=18),
                        rx.text(d, font_family="monospace", size="2"),
                        spacing="2",
                        align="center",
                        width="100%",
                        padding="6px 8px",
                        border_radius="6px",
                        cursor="pointer",
                        on_click=S.picker_enter(d),
                        _hover={"background": "var(--gray-3)"},
                    ),
                ),
                spacing="0",
                width="100%",
            ),
            rx.scroll_area(
                type="auto",
                scrollbars="vertical",
                height="260px",
                border="1px solid var(--gray-5)",
                border_radius="8px",
                padding="4px",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("arrow-up", size=16),
                    "Up",
                    on_click=S.picker_up,
                    variant="soft",
                    color_scheme="gray",
                    size="2",
                ),
                rx.button(
                    rx.icon("home", size=16),
                    "Home",
                    on_click=S.picker_home,
                    variant="soft",
                    color_scheme="gray",
                    size="2",
                ),
                rx.spacer(),
                rx.dialog.close(
                    rx.button("Cancel", variant="soft", color_scheme="gray"),
                ),
                rx.button(
                    "Select this folder",
                    rx.icon("check", size=16),
                    on_click=S.picker_select,
                    color_scheme="teal",
                ),
                justify="end",
                spacing="2",
                margin_top="12px",
                width="100%",
            ),
            max_width="540px",
        ),
        open=S.picker_open,
        on_open_change=S.set_picker_open,
    )


def dir_input(S, target: str, value=None, with_rescan: bool = True) -> rx.Component:
    """Read-only directory input + Browse (+ optional Rescan). No dialog."""
    val = S.outdir if value is None else value
    btns: list[rx.Component] = [
        rx.input(
            value=val,
            read_only=True,
            font_family="monospace",
            width="100%",
            size="3",
        ),
        rx.button(
            rx.icon("folder-open", size=16),
            "Browse…",
            on_click=S.open_picker_for(target),
            color_scheme="teal",
            size="3",
        ),
    ]
    if with_rescan:
        btns.append(
            rx.button(
                rx.icon("refresh-cw", size=16),
                on_click=S.scan,
                variant="soft",
                size="3",
            )
        )
    return rx.hstack(*btns, spacing="2", align="center", width="100%")


def dir_field(S) -> rx.Component:
    """Output-dir input + the picker dialog (single-picker pages)."""
    return rx.vstack(dir_input(S, "outdir"), dir_picker(S), width="100%")


def samples_field(S) -> rx.Component:
    """Discovered samples as toggle chips + select-all/clear."""
    return rx.vstack(
        rx.hstack(
            rx.cond(
                S.has_samples,
                rx.text(
                    S.n_selected.to_string(),
                    " / ",
                    S.n_samples.to_string(),
                    " samples selected",
                    size="2",
                    color="var(--gray-10)",
                ),
                rx.text("No samples found in this folder.",
                        size="2", color="var(--gray-10)"),
            ),
            rx.spacer(),
            rx.button("All", on_click=S.select_all_samples,
                      variant="soft", size="1"),
            rx.button("None", on_click=S.clear_samples,
                      variant="soft", size="1"),
            width="100%",
            align="center",
        ),
        rx.scroll_area(
            rx.flex(
                rx.foreach(
                    S.samples,
                    lambda s: rx.badge(
                        s,
                        color_scheme=rx.cond(S.selected.contains(s), "teal", "gray"),
                        variant=rx.cond(S.selected.contains(s), "solid", "soft"),
                        size="2",
                        cursor="pointer",
                        on_click=S.toggle_sample(s),
                    ),
                ),
                wrap="wrap",
                spacing="3",
            ),
            type="auto",
            scrollbars="vertical",
            max_height="170px",
            width="100%",
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def merged_panel(S) -> rx.Component:
    """Lists merged-results TSVs from the latest bactopia-runs (with a Refresh)."""
    return rx.card(
        rx.hstack(
            help_section("merged-results (latest run)", "merged", size="3"),
            rx.spacer(),
            rx.button(
                rx.icon("refresh-cw", size=14),
                "Refresh",
                on_click=S.refresh_merged,
                variant="soft",
                size="1",
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            S.merged.length() > 0,
            rx.vstack(
                rx.foreach(
                    S.merged,
                    lambda f: rx.hstack(
                        rx.icon("file-text", size=16, color="var(--teal-9)"),
                        rx.text(f, font_family="monospace", size="2"),
                        spacing="2",
                        align="center",
                    ),
                ),
                rx.text(S.merged_dir, size="1", color="var(--gray-9)",
                        font_family="monospace"),
                spacing="1",
                align="start",
                width="100%",
            ),
            rx.text("No merged-results yet. Run a workflow, then Refresh.",
                    size="1", color="var(--gray-9)"),
        ),
        width="100%",
    )


def _slider_field(label: str, value_var, handler, lo: int, hi: int,
                   suffix: str = "") -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(label, size="1", color="var(--gray-10)"),
            rx.badge(
                rx.cond(value_var == 0, "∞", value_var.to_string() + suffix),
                color_scheme="teal",
                variant="soft",
            ),
            spacing="2",
            align="center",
        ),
        rx.slider(
            value=[value_var],
            min=lo,
            max=hi,
            step=1,
            on_change=handler,
            color_scheme="teal",
            width="240px",
        ),
        spacing="2",
        align="start",
        width="240px",
    )


def general_params(S) -> rx.Component:
    return rx.flex(
        labeled(
            "-profile",
            rx.select(
                ["docker", "singularity", "standard"],
                value=S.profile,
                on_change=S.set_profile,
                size="3",
            ),
        ),
        _slider_field("--max_cpus (0 = ∞)", S.threads, S.set_threads, 0, _MAX_CPUS),
        _slider_field("--max_memory (0 = ∞)", S.memory, S.set_memory, 0, 256, " GB"),
        labeled(
            "-resume",
            rx.switch(S.resume, on_change=S.set_resume, color_scheme="teal"),
        ),
        wrap="wrap",
        spacing="5",
        align="end",
        width="100%",
    )
