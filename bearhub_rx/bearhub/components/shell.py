"""App shell: fixed top bar + persistent left sidebar navigation."""
from __future__ import annotations

import asyncio

import reflex as rx

from bearhub.core import system
from bearhub.data.catalog import BACTOPIA_VERSION


class ShellState(rx.State):
    """App-wide chrome state — currently just the 'Encerrar' (shutdown) flow.

    Closing the browser tab leaves the BEAR-HUB server running, so this powers an
    explicit off switch. Shutdown tears down the whole app (see system.shutdown),
    which also interrupts any active run — hence the confirmation + run warning.
    """

    confirm_open: bool = False
    shutting_down: bool = False
    # Snapshot of how many Nextflow/Bactopia runs are live, taken when the dialog
    # opens, so we can warn that shutting down will interrupt them.
    active_runs: int = 0

    @rx.event
    def open_confirm(self):
        from bearhub.core import runner

        self.active_runs = len(runner.active_run_ids())
        self.confirm_open = True

    @rx.event
    def set_confirm(self, value: bool):
        self.confirm_open = value

    @rx.event(background=True)
    async def shutdown(self):
        async with self:
            self.confirm_open = False
            self.shutting_down = True
        # Give the browser a moment to paint the "encerrado" screen before the
        # server (and this socket) goes down.
        await asyncio.sleep(1.2)
        system.shutdown()


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
            # Label hidden on narrow screens → sidebar collapses to an icon rail.
            rx.text(
                label, size="2", weight="bold" if is_active else "regular",
                display=rx.breakpoints(initial="none", md="block"),
                white_space="nowrap",
            ),
            spacing="3",
            align="center",
            width="100%",
            padding="9px 12px",
            border_radius="8px",
            background="var(--accent-4)" if is_active else "transparent",
            color="var(--accent-11)" if is_active else "var(--gray-11)",
            _hover={"background": "var(--accent-3)" if is_active else "var(--gray-3)"},
        ),
        href=href,
        underline="none",
        width="100%",
        title=label,
    )


def _sidebar(active: str) -> rx.Component:
    return rx.vstack(
        *[_nav_item(label, href, icon, active) for label, href, icon in NAV],
        rx.spacer(),
        rx.text("Bactopia", size="1", color="var(--gray-9)",
                display=rx.breakpoints(initial="none", md="block")),
        rx.badge(f"v{BACTOPIA_VERSION}", color_scheme="indigo", variant="soft"),
        spacing="1",
        padding="16px 12px",
        width=rx.breakpoints(initial="60px", md="230px"),
        height="calc(100vh - 56px)",
        border_right="1px solid var(--gray-4)",
        align="start",
        position="sticky",
        top="56px",
        flex_shrink="0",
    )


def _shutdown_dialog() -> rx.Component:
    """Confirmation before pulling the plug on the whole app."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Encerrar o BEAR-HUB?"),
            rx.alert_dialog.description(
                "Isto desliga o servidor do BEAR-HUB (interface e backend). "
                "Fechar apenas a aba do navegador não faz isso — o programa continua "
                "rodando. Para usar de novo, inicie o BEAR-HUB novamente.",
            ),
            # Extra warning only when runs are live (they'd be interrupted).
            rx.cond(
                ShellState.active_runs > 0,
                rx.callout(
                    rx.text(
                        "Há ",
                        rx.text.strong(ShellState.active_runs),
                        " análise(s) em andamento. Encerrar agora vai interrompê-las.",
                    ),
                    icon="triangle_alert",
                    color_scheme="amber",
                    margin_top="14px",
                ),
            ),
            rx.flex(
                rx.alert_dialog.cancel(
                    rx.button("Cancelar", variant="soft", color_scheme="gray"),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        rx.icon("power", size=16),
                        "Encerrar",
                        color_scheme="red",
                        on_click=ShellState.shutdown,
                    ),
                ),
                spacing="3",
                justify="end",
                margin_top="18px",
            ),
        ),
        open=ShellState.confirm_open,
        on_open_change=ShellState.set_confirm,
    )


def _topbar() -> rx.Component:
    return rx.hstack(
        rx.hstack(
            rx.text("🐻", font_size="22px"),
            rx.heading("BEAR-HUB", size="4"),
            rx.badge("Reflex", color_scheme="indigo", variant="surface", size="1"),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.color_mode.button(),
        rx.tooltip(
            rx.button(
                rx.icon("power", size=17),
                rx.text(
                    "Encerrar",
                    display=rx.breakpoints(initial="none", sm="block"),
                ),
                on_click=ShellState.open_confirm,
                color_scheme="red",
                variant="soft",
                size="2",
            ),
            content="Desligar o servidor do BEAR-HUB",
        ),
        _shutdown_dialog(),
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


def _shutdown_overlay() -> rx.Component:
    """Full-screen 'you can close this tab now' cover shown while shutting down."""
    return rx.cond(
        ShellState.shutting_down,
        rx.box(
            rx.vstack(
                rx.text("🐻", font_size="56px"),
                rx.heading("BEAR-HUB encerrado", size="7"),
                rx.text(
                    "O servidor foi desligado. Você já pode fechar esta aba com segurança.",
                    size="3",
                    color="var(--gray-11)",
                ),
                rx.text(
                    "Para usar de novo, inicie o BEAR-HUB novamente.",
                    size="2",
                    color="var(--gray-9)",
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


def shell(*content: rx.Component, active: str) -> rx.Component:
    return rx.box(
        _shutdown_overlay(),
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
                    padding=rx.breakpoints(initial="14px", md="28px"),
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
