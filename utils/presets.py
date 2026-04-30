"""
Per-page preset management for BEAR-HUB.

A Preset is a YAML-serialised subset of st.session_state. Each page gets
its own preset file under APP_STATE_DIR (so Bactopia presets don't collide
with Tools or Merlin presets).

Usage (top of a page):

    preset_mgr = PresetManager(
        ns="bactopia",
        allowed_keys=PRESET_KEYS_ALLOWLIST,
    )
    preset_mgr.apply_pending()   # replay any preset the user just clicked "Apply" on

And inside the sidebar:

    preset_mgr.render_sidebar()
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

import streamlit as st
import yaml

from constants import APP_STATE_DIR
from utils.system import ensure_state_dir


DEFAULT_PRESET_NAME = "default"


class PresetManager:
    """Load / save / apply presets for a single page namespace."""

    def __init__(
        self,
        ns: str,
        allowed_keys: Iterable[str],
        legacy_path: pathlib.Path | None = None,
    ):
        """
        Args:
            ns:           Page namespace ("bactopia", "tools", "merlin", …).
            allowed_keys: Session-state keys this page is allowed to persist.
                          Anything outside this set is never read or written.
            legacy_path:  One-time migration source. If the ns-specific file
                          doesn't exist yet but this legacy file does, its
                          contents seed the new location.
        """
        self.ns = ns
        self.allowed = frozenset(allowed_keys)
        self.path = APP_STATE_DIR / f"presets_{ns}.yaml"
        self.legacy_path = legacy_path

        # Session-state key names used internally. Namespaced so multiple
        # PresetManagers on the same page (unlikely but possible) don't collide.
        self._k_pending = f"__pending_preset_values_{ns}"
        self._k_msg = f"__preset_msg_{ns}"
        self._k_to_load = f"__preset_to_load_{ns}"
        self._k_save_name = f"__preset_save_name_{ns}"

    # ── IO ───────────────────────────────────────────────────────────────────

    def _read(self) -> dict:
        ensure_state_dir()
        if self.path.exists():
            try:
                return yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
            except Exception:
                return {}
        # One-time migration from the legacy (pre-per-page) file.
        if self.legacy_path and self.legacy_path.exists():
            try:
                legacy = yaml.safe_load(self.legacy_path.read_text(encoding="utf-8")) or {}
                if isinstance(legacy, dict) and legacy:
                    self._write(legacy)
                    return legacy
            except Exception:
                return {}
        return {}

    def _write(self, presets: dict) -> None:
        ensure_state_dir()
        self.path.write_text(
            yaml.safe_dump(presets, sort_keys=True, allow_unicode=True),
            encoding="utf-8",
        )

    def load(self) -> dict:
        """Return all presets as a dict (possibly empty)."""
        data = self._read()
        return data if isinstance(data, dict) else {}

    def save(self, name: str, values: dict) -> None:
        """Store *values* (will be filtered to allowed_keys) under *name*."""
        name = re.sub(r"\s+", "_", (name or "").strip()) or DEFAULT_PRESET_NAME
        data = self.load()
        data[name] = {k: v for k, v in values.items() if k in self.allowed}
        self._write(data)

    def delete(self, name: str) -> bool:
        """Remove *name* from the preset store. Returns True if removed."""
        data = self.load()
        if name in data:
            del data[name]
            self._write(data)
            return True
        return False

    # ── Session-state integration ────────────────────────────────────────────

    def _snapshot(self) -> dict:
        """Current session_state, filtered to allowed keys."""
        return {k: st.session_state[k] for k in self.allowed if k in st.session_state}

    def apply_pending(self) -> None:
        """
        Apply any staged preset values to session_state.

        Must be called before the page's widgets render; otherwise Streamlit
        treats the pre-existing widget state as authoritative and ignores
        the newly-written values.
        """
        pending = st.session_state.pop(self._k_pending, None)
        if not pending:
            return
        for k, v in pending.items():
            if k in self.allowed:
                st.session_state[k] = v
        st.session_state.setdefault(self._k_msg, "Preset applied.")

    # ── UI callbacks ─────────────────────────────────────────────────────────

    def _cb_stage_apply(self) -> None:
        name = st.session_state.get(self._k_to_load)
        if not name or name == "(none)":
            return
        st.session_state[self._k_pending] = self.load().get(name, {})
        st.session_state[self._k_msg] = f"Preset staged: {name} (applied on this reload)"

    def _cb_save(self) -> None:
        name = st.session_state.get(self._k_save_name) or DEFAULT_PRESET_NAME
        self.save(name, self._snapshot())
        normalized = re.sub(r"\s+", "_", name.strip()) or DEFAULT_PRESET_NAME
        st.session_state[self._k_msg] = f"Preset saved: {normalized}"

    def _cb_delete(self) -> None:
        name = st.session_state.get(self._k_to_load)
        if not name or name == "(none)":
            return
        if self.delete(name):
            st.session_state[self._k_msg] = f"Preset deleted: {name}"

    # ── Rendering ────────────────────────────────────────────────────────────

    def render_sidebar(self, header: str = "Presets") -> None:
        """Render the Load / Save / Delete controls in the current container."""
        st.header(header)
        names = sorted(self.load().keys())
        st.selectbox("Load preset", ["(none)"] + names, key=self._k_to_load)
        st.text_input(
            "Save as (preset name)",
            key=self._k_save_name,
            placeholder="e.g., my_preset",
        )

        # Wrap the buttons in an anchor div so pages can target them with CSS
        # (matches the old BACTOPIA.py styling for width: 100% sidebar buttons).
        anchor = f"presets-section-{self.ns}"
        st.markdown(f'<div id="{anchor}">', unsafe_allow_html=True)
        st.button("Apply", key=f"__btn_apply_{self.ns}", on_click=self._cb_stage_apply)
        st.button("Save current", key=f"__btn_save_{self.ns}", on_click=self._cb_save)
        st.button("Delete", key=f"__btn_delete_{self.ns}", on_click=self._cb_delete)
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get(self._k_msg):
            st.caption(st.session_state[self._k_msg])
