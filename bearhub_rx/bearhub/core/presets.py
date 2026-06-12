"""Named parameter presets, persisted to ~/.bactopia_ui_local/presets.json.

A preset is a namespaced snapshot of a page's parameter config (e.g. the main
pipeline's bopts/bflags) so users can save and reuse setups like
"S. pyogenes default" or "E. coli hybrid".
"""
from __future__ import annotations

import json

from bearhub.core.system import APP_STATE_DIR

_FILE = APP_STATE_DIR / "presets.json"


def _load_all() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_all(data: dict) -> None:
    APP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_presets(ns: str) -> list[str]:
    return sorted(_load_all().get(ns, {}).keys())


def save_preset(ns: str, name: str, payload: dict) -> None:
    data = _load_all()
    data.setdefault(ns, {})[name] = payload
    _save_all(data)


def get_preset(ns: str, name: str) -> dict | None:
    return _load_all().get(ns, {}).get(name)


def delete_preset(ns: str, name: str) -> None:
    data = _load_all()
    if ns in data and name in data[ns]:
        del data[ns][name]
        _save_all(data)
