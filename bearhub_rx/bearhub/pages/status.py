"""Status page — installed versions."""
from __future__ import annotations

import reflex as rx

from bearhub.components.shell import shell
from bearhub.components.wizard import hero
from bearhub.data.catalog import BACTOPIA_VERSION
from bearhub.state import StatusState

_ROWS = [
    ("Bactopia", "bactopia"),
    ("Nextflow",  "nextflow"),
    ("Java",      "java"),
    ("Docker",    "docker"),
]


def _version_row(label: str, key: str) -> rx.Component:
    return rx.hstack(
        rx.text(label, weight="bold", size="2", width="120px"),
        rx.code(StatusState.versions.get(key, "Unknown")),
        spacing="3",
        align="center",
        width="100%",
    )


def _update_banner() -> rx.Component:
    """Informational 'update available' callout (only when a newer tag exists)."""
    return rx.cond(
        StatusState.update_available,
        rx.callout(
            rx.text(
                "Update available (",
                StatusState.app_version,
                " → ",
                StatusState.latest_version,
                ") — run ",
                rx.code("bash update_bear.sh"),
                " or ",
                rx.code("make update"),
                ".",
            ),
            icon="circle-arrow-up",
            color_scheme="teal",
            variant="surface",
            width="100%",
            margin_bottom="3",
        ),
    )


def status_page() -> rx.Component:
    return shell(
        hero("activity", "System Status",
             "Versions of Bactopia and its dependencies."),
        _update_banner(),
        rx.card(
            rx.hstack(
                rx.text("BEAR-HUB", weight="bold", size="2", width="120px"),
                rx.code(rx.cond(StatusState.app_version != "", StatusState.app_version, "unknown")),
                spacing="3",
                align="center",
                width="100%",
            ),
            margin_bottom="3",
            width="100%",
        ),
        rx.card(
            rx.hstack(
                rx.heading("External tools", size="4"),
                rx.spacer(),
                rx.cond(
                    StatusState.loading,
                    rx.spinner(size="2"),
                ),
                rx.button(
                    rx.icon("refresh-cw", size=16),
                    "Refresh",
                    on_click=StatusState.load,
                    variant="soft",
                    size="2",
                ),
                width="100%",
                align="center",
            ),
            rx.divider(margin_y="3"),
            rx.vstack(
                *[_version_row(l, k) for l, k in _ROWS],
                spacing="3",
                width="100%",
            ),
            width="100%",
        ),
        active="/status",
    )
