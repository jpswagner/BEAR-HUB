"""Hub landing page — entry cards for each tool."""
from __future__ import annotations

import reflex as rx

from bearhub.components.shell import shell
from bearhub.data.catalog import BACTOPIA_VERSION, TOOLS

CARDS = [
    ("Bactopia", "/bactopia", "dna",
     "Run the main pipeline: QC, assembly, annotation and typing from raw reads."),
    ("Bactopia Tools", "/tools", "wrench",
     f"Run any of {len(TOOLS)} official --wf tools over already-processed samples."),
    ("MERLIN", "/merlin", "wand-sparkles",
     "Species-specific typing workflows, selected automatically per genus."),
    ("Status", "/status", "activity",
     "Check Bactopia, Nextflow, Java and Docker versions."),
]


def _card(title: str, href: str, icon: str, desc: str) -> rx.Component:
    # height="100%" lets every card fill its grid cell so all cards match size.
    return rx.link(
        rx.card(
            rx.hstack(
                rx.box(
                    rx.icon(icon, size=26, color="white"),
                    padding="12px",
                    border_radius="12px",
                    background="linear-gradient(135deg,#0f766e,#134e4a)",
                ),
                rx.vstack(
                    rx.heading(title, size="4"),
                    rx.text(desc, size="2", color="var(--gray-10)"),
                    spacing="1",
                    align="start",
                ),
                spacing="4",
                align="center",
                width="100%",
            ),
            width="100%",
            height="100%",
            _hover={"border_color": "var(--teal-8)"},
        ),
        href=href,
        underline="none",
        width="100%",
        height="100%",
    )


def hub_page() -> rx.Component:
    return shell(
        rx.box(
            rx.hstack(
                rx.text("🧬", font_size="34px"),
                rx.vstack(
                    rx.heading("BEAR-HUB", size="7", color="white"),
                    rx.text(
                        "A friendly interface to orchestrate Bactopia analyses.",
                        size="3",
                        color="white",
                        opacity="0.9",
                    ),
                    spacing="0",
                    align="start",
                ),
                rx.spacer(),
                rx.badge(
                    f"Bactopia v{BACTOPIA_VERSION}",
                    color_scheme="teal",
                    variant="surface",
                    size="2",
                ),
                spacing="4",
                align="center",
                width="100%",
            ),
            padding="28px",
            border_radius="18px",
            width="100%",
            background="linear-gradient(135deg,#0f766e 0%,#115e59 55%,#134e4a 100%)",
            box_shadow="0 10px 30px rgba(15,118,110,.3)",
        ),
        # Equal-size cards: 2 equal columns + equal row heights (gridAutoRows: 1fr)
        # combined with height="100%" on each card.
        rx.grid(
            *[_card(*c) for c in CARDS],
            columns="2",
            spacing="4",
            width="100%",
            align="stretch",
            style={"gridAutoRows": "1fr"},
        ),
        rx.text(
            "BEAR-HUB only provides a UI to orchestrate analyses with Bactopia, "
            "third-party software maintained independently by its authors.",
            size="1",
            color="var(--gray-9)",
        ),
        active="/",
    )
