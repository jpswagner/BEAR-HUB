"""
Page-level boilerplate for BEAR-HUB.

Every page (pages/BACTOPIA.py, pages/BACTOPIA-TOOLS.py, …) used to repeat the
same 40-50 lines of setup: st.set_page_config, APP_ROOT discovery, env
bootstrap, NXF_HOME, session-state defaults. init_page() collapses that to a
single call.

Usage (top of any page):

    import utils
    utils.init_page(
        title="Bactopia",
        icon="🦠",
        ns="bactopia",
        defaults={"profile": "docker", "outdir": DEFAULT_OUTDIR, ...},
    )
"""

from __future__ import annotations

import os
import pathlib

import streamlit as st

from utils.system import (
    bootstrap_bear_env_from_file,
    docker_available,
    ensure_nxf_home,
    get_nextflow_bin,
    init_session_state,
    nextflow_available,
)
from utils.registry import Tool, load_tools


# ── Project-root discovery (same logic each page used to repeat) ──────────────

def _discover_project_root() -> pathlib.Path:
    """
    Return the project root (the folder that holds `static/` and `tools.yaml`).

    Pages live in pages/, the hub lives at the project root; both work.
    """
    here = pathlib.Path(__file__).resolve().parent  # utils/
    candidate = here.parent                          # project root
    if (candidate / "tools.yaml").is_file() or (candidate / "static").is_dir():
        return candidate
    # Fallback: current working directory
    return pathlib.Path.cwd()


PROJECT_ROOT = _discover_project_root()


# ── init_page ─────────────────────────────────────────────────────────────────

def init_page(
    *,
    title: str,
    icon: str = "🐻",
    ns: str | None = None,
    defaults: dict | None = None,
    page_title: str | None = None,
    with_sidebar_nav: bool = True,
) -> pathlib.Path:
    """
    One-call setup for a BEAR-HUB page.

    - Sets st.set_page_config.
    - Loads ~/.bear-hub/config.env (BACTOPIA_ENV_PREFIX, NXF_CONDA_EXE, …).
    - Ensures NXF_HOME is writable.
    - Seeds session-state defaults.
    - Renders the tool sidebar nav (can be disabled for standalone use).

    Args:
        title:             Display title for the browser tab ("Bactopia").
        icon:              Page favicon emoji.
        ns:                Tool id (must match an entry in tools.yaml); used
                           to highlight the current tool in the sidebar nav.
        defaults:          Session-state defaults (forwarded to
                           init_session_state).
        page_title:        Overrides the auto-built "BEAR-HUB — {title}".
        with_sidebar_nav:  Whether to render the global tool nav.

    Returns:
        The resolved project root, so pages can use it to find static/ assets.
    """
    st.set_page_config(
        page_title=page_title or f"BEAR-HUB — {title}",
        page_icon=icon,
        layout="wide",
    )

    bootstrap_bear_env_from_file()
    ensure_nxf_home()

    if defaults:
        init_session_state(defaults)

    if with_sidebar_nav:
        render_tool_sidebar(current_id=ns)

    return PROJECT_ROOT


# ── Sidebar nav (shared across pages) ─────────────────────────────────────────

def _env_badge_block() -> None:
    """Render a compact Nextflow/Docker/env status block in the sidebar."""
    nf_ok = nextflow_available()
    docker_ok = docker_available()
    st.write(f"Nextflow: {'✅' if nf_ok else '❌'} | Docker: {'✅' if docker_ok else '❌'}")

    if not nf_ok:
        st.error("Nextflow not found (PATH or BACTOPIA_ENV_PREFIX).", icon="⚠️")
    else:
        nf_bin = get_nextflow_bin()
        if nf_bin != "nextflow":
            st.caption(f"Nextflow: `{nf_bin}`")

    if not docker_ok:
        st.error("Docker not available.", icon="⚠️")

    bactopia_env_prefix = os.environ.get("BACTOPIA_ENV_PREFIX")
    if bactopia_env_prefix:
        st.caption(f"BACTOPIA_ENV_PREFIX: `{bactopia_env_prefix}`")


def render_tool_sidebar(current_id: str | None = None) -> None:
    """
    Render the global tool-nav sidebar.

    Every registered tool gets a button. The current tool (matched by
    `current_id`) is rendered as `primary` to highlight it; others are
    `secondary`. A "← Hub" link and the env-status badges appear above.
    """
    tools = load_tools()

    with st.sidebar:
        if st.button("🏠 Hub", key="__nav_hub", width="stretch"):
            st.switch_page("BEAR-HUB.py")

        st.divider()
        st.caption("Tools")

        for tool in tools:
            if not tool.exists(PROJECT_ROOT):
                continue
            is_current = (tool.id == current_id)
            label = f"{tool.icon} {tool.name}{tool.status_badge}"
            btn_type = "primary" if is_current else "secondary"
            # The current page's button is disabled (we're already here).
            if st.button(
                label,
                key=f"__nav_{tool.id}",
                type=btn_type,
                width="stretch",
                disabled=is_current,
            ):
                st.switch_page(tool.page)

        st.divider()
        st.caption("Environment")
        _env_badge_block()


# Re-export Tool type for convenience in pages that want to introspect the registry.
__all__ = ["init_page", "render_tool_sidebar", "PROJECT_ROOT", "Tool"]
