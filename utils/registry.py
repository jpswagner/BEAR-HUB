"""
Tool registry for BEAR-HUB.

Loads tools.yaml from the project root and returns a list of Tool
dataclasses describing every module the hub exposes. The hub and the
per-page sidebar nav both iterate this list, so adding a new tool is
a single YAML append plus a pages/<NAME>.py file.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import List

import yaml


# Project root = parent of utils/
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TOOLS_YAML = _PROJECT_ROOT / "tools.yaml"


@dataclass(frozen=True)
class Tool:
    """A single registered tool."""

    id: str
    name: str
    page: str
    icon: str = "🧬"
    status: str = "stable"            # stable | beta | wip
    tagline: str | None = None
    description: str = ""
    category: str = "other"

    @property
    def status_badge(self) -> str:
        """Unicode badge for the tool's status ('' for stable)."""
        return {"wip": " 🚧", "beta": " 🧪", "stable": ""}.get(self.status, "")

    @property
    def button_type(self) -> str:
        """Streamlit button type — 'primary' for stable, 'secondary' otherwise."""
        return "primary" if self.status == "stable" else "secondary"

    @property
    def is_disabled(self) -> bool:
        """Whether navigation to this tool should be blocked (wip)."""
        return self.status == "wip"

    def exists(self, root: pathlib.Path | None = None) -> bool:
        """True if the page file for this tool exists on disk."""
        base = root or _PROJECT_ROOT
        return (base / self.page).is_file()


def load_tools(path: pathlib.Path | None = None) -> List[Tool]:
    """
    Load the tool registry from tools.yaml.

    Returns an empty list on any I/O or parse error — the caller can
    decide whether to render an empty hub or surface a warning.
    """
    target = path or _TOOLS_YAML
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    if not isinstance(raw, list):
        return []

    tools: List[Tool] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            tools.append(Tool(
                id=str(entry["id"]),
                name=str(entry["name"]),
                page=str(entry["page"]),
                icon=str(entry.get("icon", "🧬")),
                status=str(entry.get("status", "stable")),
                tagline=(str(entry["tagline"]) if entry.get("tagline") else None),
                description=str(entry.get("description", "")).strip(),
                category=str(entry.get("category", "other")),
            ))
        except KeyError:
            # A malformed entry is skipped rather than crashing the hub.
            continue
    return tools


def find_tool(tool_id: str, tools: List[Tool] | None = None) -> Tool | None:
    """Look up a tool by id. Loads the registry if none was passed."""
    for t in (tools if tools is not None else load_tools()):
        if t.id == tool_id:
            return t
    return None
