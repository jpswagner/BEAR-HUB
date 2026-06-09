"""App shell: fixed top bar + persistent left sidebar navigation."""
from __future__ import annotations

import reflex as rx

from bearhub.data.catalog import BACTOPIA_VERSION

NAV = [
    ("Hub",            "/",         "house"),
    ("Bactopia",       "/bactopia", "dna"),
    ("Bactopia Tools", "/tools",    "wrench"),
    ("MERLIN",         "/merlin",   "wand-sparkles"),
    ("Runs",           "/runs",     "history"),
    ("Status",         "/status",   "activity"),
]


def _nav_item(label: str, href: str, icon: str, active: str) -> rx.Component:
    is_active = href == active
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=18),
            rx.text(label, size="2", weight="bold" if is_active else "regular"),
            spacing="3",
            align="center",
            width="100%",
            padding="9px 12px",
            border_radius="8px",
            background="var(--teal-4)" if is_active else "transparent",
            color="var(--teal-11)" if is_active else "var(--gray-11)",
            _hover={"background": "var(--teal-3)" if is_active else "var(--gray-3)"},
        ),
        href=href,
        underline="none",
        width="100%",
    )


def _sidebar(active: str) -> rx.Component:
    return rx.vstack(
        *[_nav_item(label, href, icon, active) for label, href, icon in NAV],
        rx.spacer(),
        rx.text("Bactopia", size="1", color="var(--gray-9)"),
        rx.badge(f"v{BACTOPIA_VERSION}", color_scheme="teal", variant="soft"),
        spacing="1",
        padding="16px 12px",
        width="230px",
        height="calc(100vh - 56px)",
        border_right="1px solid var(--gray-4)",
        align="start",
        position="sticky",
        top="56px",
    )


def _topbar() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.text("🐻", font_size="22px"),
            rx.heading("BEAR-HUB", size="4"),
            rx.badge("Reflex", color_scheme="teal", variant="surface", size="1"),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.color_mode.button(),
        align="center",
        width="100%",
        height="56px",
        padding="0 20px",
        border_bottom="1px solid var(--gray-4)",
        position="sticky",
        top="0",
        background="var(--color-background)",
        z_index="20",
    )


def shell(*content: rx.Component, active: str) -> rx.Component:
    return rx.box(
        _topbar(),
        rx.hstack(
            _sidebar(active),
            rx.box(
                rx.vstack(
                    *content,
                    spacing="7",
                    width="100%",
                    max_width="1080px",
                    margin="0 auto",
                    padding="28px",
                ),
                flex="1",
                height="calc(100vh - 56px)",
                overflow="auto",
            ),
            spacing="0",
            align="start",
            width="100%",
        ),
        width="100%",
    )
