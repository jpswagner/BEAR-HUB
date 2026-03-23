"""
File-system browser widget for BEAR-HUB.

Provides an interactive path picker (file or directory) rendered as a
Streamlit dialog or inline expander.
"""

import os
import html
import hashlib
import fnmatch
import pathlib

import streamlit as st


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_id(s: str) -> str:
    """Short hash suitable for use as a DOM element ID."""
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


def _list_dir(cur: pathlib.Path) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Return (sorted_dirs, sorted_files) for the given directory."""
    try:
        entries = list(cur.iterdir())
    except Exception:
        entries = []
    dirs = sorted([p for p in entries if p.is_dir()], key=lambda p: p.name.lower())
    files = sorted([p for p in entries if p.is_file()], key=lambda p: p.name.lower())
    return dirs, files


def _st_rerun() -> None:
    """Trigger a Streamlit script rerun (compatible with older versions)."""
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()


# ── Core browser UI ───────────────────────────────────────────────────────────

def _fs_browser_core(
    label: str,
    key: str,
    mode: str = "file",
    start: str | None = None,
    patterns: list[str] | None = None,
) -> None:
    """
    Render the interactive file-system browser.

    Args:
        label:    Display label for the picker.
        key:      Unique Streamlit session state key.
        mode:     "file" to pick a file; "dir" to pick a directory.
        start:    Initial path (falls back to session state or CWD).
        patterns: Glob patterns for file filtering (e.g. ["*.fastq.gz"]).
    """
    base_start = start or st.session_state.get(key) or os.getcwd()
    cur_key = f"__picker_cur__{key}"
    try:
        cur = pathlib.Path(st.session_state.get(cur_key, base_start)).expanduser().resolve()
    except Exception:
        cur = pathlib.Path(base_start).expanduser().resolve()

    def set_cur(p: pathlib.Path) -> None:
        st.session_state[cur_key] = str(p.expanduser().resolve())

    hostfs_root = os.getenv("HOSTFS_ROOT", "/hostfs")
    c_up, c_home, c_host, c_path, _ = st.columns([0.9, 0.9, 0.9, 6, 2])

    with c_up:
        parent = cur.parent if cur.parent != cur else cur
        st.button("⬆️ Up", key=f"{key}_up", on_click=set_cur, args=(parent,))
    with c_home:
        home_base = pathlib.Path(start or pathlib.Path.home())
        st.button("🏠 Home", key=f"{key}_home", on_click=set_cur, args=(home_base,))
    with c_host:
        if os.path.exists(hostfs_root):
            st.button("🖥 Host", key=f"{key}_host", on_click=set_cur, args=(pathlib.Path(hostfs_root),))
    with c_path:
        st.caption(str(cur))

    dirs, files = _list_dir(cur)

    if patterns:
        norm_patterns = [p if p.startswith("*") else f"*{p}" for p in patterns]
        files = [f for f in files if any(fnmatch.fnmatch(f.name.lower(), pat.lower()) for pat in norm_patterns)]
    elif mode == "dir":
        files = []

    st.markdown("**Folders**")
    if not dirs:
        st.caption("No folders found")
    else:
        dcols = st.columns(2)
        for i, d in enumerate(dirs):
            did = _safe_id(str(d))
            dcols[i % 2].button("📁 " + d.name, key=f"{key}_d_{did}", on_click=set_cur, args=(d,))

    st.markdown("**Files**")
    if not files:
        st.caption("No matching files found")
    else:
        if mode == "file":
            for f in files:
                fid = _safe_id(str(f))
                if st.button("📄 " + f.name, key=f"{key}_f_{fid}"):
                    st.session_state[key] = str(f.resolve())
                    st.session_state[f"__open_{key}"] = False
                    _st_rerun()
        else:
            for f in files:
                st.markdown(
                    f"<span style='color:gray; margin-left:4px;'>📄 {html.escape(f.name)}</span>",
                    unsafe_allow_html=True,
                )


# ── Public widget ─────────────────────────────────────────────────────────────

def path_picker(
    label: str,
    key: str,
    mode: str = "dir",
    start: str | None = None,
    patterns: list[str] | None = None,
    help: str | None = None,
) -> str:
    """
    Render a path picker widget (text input + Browse button).

    Args:
        label:    Widget label.
        key:      Unique session state key.
        mode:     "file" or "dir".
        start:    Initial path hint.
        patterns: File glob patterns (only relevant when mode="file").
        help:     Tooltip text.

    Returns:
        The selected path string (may be empty if nothing is selected yet).
    """
    col1, col2 = st.columns([7, 2])
    with col1:
        if key in st.session_state:
            val = st.text_input(label, key=key, help=help)
        else:
            val = st.text_input(label, value=start or "", key=key, help=help)
        try:
            if val:
                val_abs = str(pathlib.Path(val).expanduser().resolve())
                if val_abs != val:
                    st.session_state[key] = val_abs
        except Exception:
            pass

    def _cb_open() -> None:
        st.session_state[f"__just_opened_{key}"] = True
        st.session_state[f"__open_{key}"] = True
        try:
            hint = pathlib.Path(st.session_state.get(key) or start or os.getcwd())
            st.session_state[f"__picker_cur__{key}"] = str(
                (hint if hint.is_dir() else hint.parent).expanduser().resolve()
            )
        except Exception:
            st.session_state[f"__picker_cur__{key}"] = str(
                pathlib.Path(start or os.getcwd()).expanduser().resolve()
            )

    with col2:
        st.button("Browse…", key=f"open_{key}", on_click=_cb_open)

    if hasattr(st, "dialog"):
        just_opened = st.session_state.get(f"__just_opened_{key}", False)
        if just_opened:
            st.session_state[f"__just_opened_{key}"] = False

            @st.dialog(label, width="large")
            def _dlg() -> None:
                _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
                c_ok, c_cancel = st.columns(2)
                with c_ok:
                    if st.button("✅ Use this path", key=f"use_{key}"):
                        if mode == "dir":
                            cur = pathlib.Path(st.session_state.get(f"__picker_cur__{key}", start or os.getcwd()))
                            st.session_state[key] = str(cur.expanduser().resolve())
                        st.session_state[f"__open_{key}"] = False
                        _st_rerun()
                with c_cancel:
                    if st.button("Cancel", key=f"cancel_{key}"):
                        st.session_state[f"__open_{key}"] = False
                        _st_rerun()

            _dlg()
        else:
            st.session_state[f"__open_{key}"] = False
    elif st.session_state.get(f"__open_{key}", False):
        st.info(f"{label} (inline mode)")
        _fs_browser_core(label, key, mode=mode, start=start, patterns=patterns)
        if st.button("✅ Use this path", key=f"use_inline_{key}"):
            if mode == "dir":
                cur = pathlib.Path(st.session_state.get(f"__picker_cur__{key}", start or os.getcwd()))
                st.session_state[key] = str(cur.expanduser().resolve())
            st.session_state[f"__open_{key}"] = False
            _st_rerun()

    return st.session_state.get(key) or ""
