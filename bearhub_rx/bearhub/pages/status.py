"""Status page — installed versions + in-app updater."""
from __future__ import annotations

import reflex as rx

from bearhub.components.shell import shell
from bearhub.components.wizard import hero
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
                ") — use the ",
                rx.text.strong("Update & verify"),
                " button below.",
            ),
            icon="circle-arrow-up",
            color_scheme="indigo",
            variant="surface",
            width="100%",
            margin_bottom="3",
        ),
    )


# ── In-app updater ─────────────────────────────────────────────────────────────

def _update_dialog() -> rx.Component:
    """Confirmation before pulling a new version and restarting the app."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Update BEAR-HUB?"),
            rx.alert_dialog.description(
                "This pulls the latest version from git, re-runs the installer "
                "(which re-checks Docker, Nextflow, Bactopia and the conda "
                "environments), then restarts the app automatically.",
            ),
            # What is preserved — the point of the whole feature.
            rx.callout(
                rx.text(
                    "Your data is kept: run history, live logs and presets live in ",
                    rx.code("~/.bactopia_ui_local"),
                    " (outside the repo), and results (",
                    rx.code("bactopia_out/"), ", ", rx.code("data/"), ", ",
                    rx.code("work/"),
                    ") are ignored by git. Only the frontend build cache is rebuilt.",
                ),
                icon="info",
                color_scheme="green",
                size="1",
                margin_top="14px",
            ),
            # Active runs would be interrupted (the updater stops the app).
            rx.cond(
                StatusState.active_runs > 0,
                rx.callout(
                    rx.text(
                        "There are ",
                        rx.text.strong(StatusState.active_runs),
                        " run(s) in progress. Updating restarts the app and will "
                        "interrupt them — their Nextflow work dirs are kept, so you "
                        "can resume afterwards with -resume.",
                    ),
                    icon="triangle_alert",
                    color_scheme="amber",
                    size="1",
                    margin_top="10px",
                ),
            ),
            # Local edits are stashed and restored by update_bear.sh.
            rx.cond(
                StatusState.git_dirty,
                rx.callout(
                    "Local changes detected in the checkout — they are stashed "
                    "before the pull and restored afterwards.",
                    icon="triangle_alert",
                    color_scheme="amber",
                    size="1",
                    margin_top="10px",
                ),
            ),
            rx.flex(
                rx.alert_dialog.cancel(
                    rx.button("Cancel", variant="soft", color_scheme="gray"),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.icon("circle-arrow-up", size=16),
                        "Update & restart",
                        color_scheme="indigo",
                        on_click=StatusState.start_update,
                    ),
                ),
                spacing="3",
                justify="end",
                margin_top="18px",
            ),
            max_width="560px",
        ),
        open=StatusState.update_confirm_open,
        on_open_change=StatusState.set_update_confirm,
    )


def _updating_overlay() -> rx.Component:
    """Full-screen cover while the detached updater runs (this app goes down)."""
    return rx.cond(
        StatusState.updating,
        rx.box(
            rx.vstack(
                rx.spinner(size="3"),
                rx.heading("Updating BEAR-HUB…", size="7"),
                rx.text(
                    "Pulling the new version, re-checking the installation and "
                    "restarting. This takes 1–2 minutes.",
                    size="3", color="var(--gray-11)",
                ),
                rx.text(
                    "This page disconnects while the app restarts — just reload it in "
                    "a minute. Your runs and results are untouched.",
                    size="2", color="var(--gray-9)",
                ),
                spacing="3",
                align="center",
            ),
            position="fixed",
            inset="0",
            display="flex",
            align_items="center",
            justify_content="center",
            text_align="center",
            padding="24px",
            background="var(--color-background)",
            z_index="9999",
        ),
    )


def _kv(label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label, weight="bold", size="2", width="120px"),
        value,
        spacing="3", align="center", width="100%",
    )


def _update_card() -> rx.Component:
    return rx.card(
        rx.hstack(
            rx.heading("App & updates", size="4"),
            rx.spacer(),
            rx.cond(
                StatusState.update_available,
                rx.badge("update available", color_scheme="indigo", variant="solid"),
            ),
            width="100%", align="center",
        ),
        rx.divider(margin_y="3"),
        rx.vstack(
            _kv("BEAR-HUB", rx.code(rx.cond(StatusState.app_version != "",
                                            StatusState.app_version, "unknown"))),
            rx.cond(
                StatusState.git_is_repo,
                rx.vstack(
                    _kv("Branch", rx.code(StatusState.git_branch)),
                    _kv("Commit", rx.code(StatusState.git_ref)),
                    spacing="3", width="100%",
                ),
            ),
            spacing="3", width="100%",
        ),
        rx.cond(
            StatusState.git_is_repo,
            rx.flex(
                rx.button(
                    rx.icon("circle-arrow-up", size=16),
                    "Update & verify",
                    on_click=StatusState.open_update_confirm,
                    color_scheme="indigo",
                    size="2",
                ),
                rx.text(
                    "Pulls from git, re-verifies the install, restarts. "
                    "Runs and results are preserved.",
                    size="1", color="var(--gray-10)",
                ),
                spacing="3", align="center", wrap="wrap", margin_top="14px",
            ),
            rx.callout(
                "This is not a git checkout, so in-app updates are unavailable. "
                "Re-clone from GitHub to enable them.",
                icon="triangle_alert", color_scheme="amber", size="1", margin_top="14px",
            ),
        ),
        width="100%",
        margin_bottom="3",
    )


def _update_log_panel() -> rx.Component:
    """Last update's output — the 'review the installation' record."""
    return rx.cond(
        StatusState.has_update_log,
        rx.accordion.root(
            rx.accordion.item(
                header=rx.hstack(
                    rx.text("Last update log", size="2", weight="bold"),
                    rx.text("installer + dependency verification output",
                            size="1", color="var(--gray-9)", margin_left="8px"),
                    align="center",
                ),
                content=rx.scroll_area(
                    rx.code_block(
                        StatusState.update_log_text,
                        language="bash", width="100%", wrap_long_lines=True,
                        font_size="11px",
                    ),
                    type="always", scrollbars="both", max_height="420px", width="100%",
                ),
            ),
            collapsible=True,
            width="100%",
            variant="ghost",
        ),
    )


def status_page() -> rx.Component:
    return shell(
        _updating_overlay(),
        hero("activity", "System Status",
             "Versions of Bactopia and its dependencies, and app updates."),
        _update_banner(),
        _update_card(),
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
        _update_log_panel(),
        _update_dialog(),
        active="/status",
    )
