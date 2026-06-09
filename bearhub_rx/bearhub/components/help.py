"""Help popover ("?") with colored text + section headers (data/help_texts)."""
from __future__ import annotations

import re

import reflex as rx

from bearhub.data.help_texts import HELP

_FLAG = re.compile(r"(--?[A-Za-z][\w-]*)")


def _inline(text: str) -> list[rx.Component]:
    """Color flag-like tokens (--scheme, -M, …) inside a line."""
    text = text.replace("**", "").replace("`", "")
    spans = []
    last = 0
    for m in _FLAG.finditer(text):
        if m.start() > last:
            spans.append(rx.text.span(text[last:m.start()]))
        spans.append(rx.text.span(
            m.group(1),
            style={"color": "var(--teal-11)", "fontFamily": "monospace", "fontWeight": "600"},
        ))
        last = m.end()
    if last < len(text):
        spans.append(rx.text.span(text[last:]))
    return spans if spans else [rx.text.span(text)]


def render_help(md: str) -> rx.Component:
    """Render our help markdown as colored Reflex text (no react-markdown)."""
    blocks = []
    for line in md.split("\n"):
        line = line.rstrip()
        # Horizontal rule / separator
        if not line.strip():
            blocks.append(rx.box(height="4px"))
            continue
        # Bold heading: **text**
        heading_m = re.fullmatch(r"\*\*(.+?)\*\*", line.strip())
        if heading_m:
            blocks.append(rx.text(
                heading_m.group(1),
                weight="bold",
                size="3",
                style={"color": "var(--teal-11)"},
            ))
            continue
        # Bullet list item
        if line.startswith("- "):
            content = line[2:]
            blocks.append(rx.text(
                "• ",
                *_inline(content),
                style={"color": "var(--amber-9)", "fontWeight": "700"},
            ))
            continue
        # Normal line
        blocks.append(rx.text(
            *_inline(line),
            size="2",
            style={"color": "var(--gray-12)", "lineHeight": "1.5"},
        ))
    return rx.vstack(*blocks, spacing="1", align="start", width="100%")


def help_button(key: str | None) -> rx.Component:
    md = HELP.get(key) if key else None
    if not md:
        return rx.fragment()
    return rx.popover.root(
        rx.popover.trigger(
            rx.icon("circle-help", size=15, color="var(--teal-9)",
                    style={"cursor": "pointer"}),
        ),
        rx.popover.content(
            rx.scroll_area(
                rx.box(render_help(md), padding_right="10px"),
                scrollbars="vertical",
                style={"maxHeight": "360px"},
            ),
            width="460px",
            side="right",
            align="start",
        ),
    )


def section(title: str, key: str | None = None, size: str = "3") -> rx.Component:
    """A heading with an optional inline help button."""
    return rx.hstack(
        rx.heading(title, size=size),
        help_button(key) if key else rx.fragment(),
        spacing="2",
        align="center",
    )


def field_label(label: str, key: str | None = None) -> rx.Component:
    """Small field caption with an optional help button."""
    return rx.hstack(
        rx.text(label, size="1", color="var(--gray-10)"),
        help_button(key) if key else rx.fragment(),
        spacing="1",
        align="center",
    )
