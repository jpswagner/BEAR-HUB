"""Detect installed tool versions for the Status page."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import urllib.request

from bearhub.core.system import get_bactopia_bin, get_env_bin, get_nextflow_bin
from bearhub.data.catalog import GITHUB_REPO

# bearhub_rx/bearhub/core/ -> repo root (BEAR-HUB), where the VERSION file lives.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _run(args: list[str]) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def _normalize(tag: str) -> str:
    """Strip a leading 'v' so 'v2.0.0' and '2.0.0' compare equal."""
    return tag.strip().lstrip("vV")


def _version_tuple(tag: str) -> tuple[int, ...]:
    """Best-effort numeric tuple for comparing semver-ish tags."""
    parts = re.findall(r"\d+", _normalize(tag))
    return tuple(int(p) for p in parts) if parts else (0,)


def get_app_version() -> str:
    """Read the BEAR-HUB app version from the repo VERSION file (e.g. 'v2.0.0')."""
    try:
        return (_REPO_ROOT / "VERSION").read_text().strip() or "unknown"
    except OSError:
        return "unknown"


def check_for_update(timeout: float = 4.0) -> dict[str, str]:
    """Best-effort 'is a newer release available?' check against GitHub.

    Returns {"current", "latest", "available"} where "available" is "yes"/"no"/
    "unknown". All network/parse errors are swallowed (offline labs must never
    see an error) and reported as "unknown".
    """
    current = get_app_version()
    result = {"current": current, "latest": "", "available": "unknown"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "BEAR-HUB-update-check"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest = str(data.get("tag_name") or "").strip()
    except Exception:
        return result  # offline / no releases / API error → "unknown"
    if not latest:
        return result
    result["latest"] = latest
    if current == "unknown":
        result["available"] = "unknown"
    elif _version_tuple(latest) > _version_tuple(current):
        result["available"] = "yes"
    else:
        result["available"] = "no"
    return result


def get_versions() -> dict[str, str]:
    out: dict[str, str] = {}

    nf = get_nextflow_bin()
    nf_out = _run([nf, "-version"])
    m = re.search(r"version\s+([\d.]+(?:\.[\w]+)?)", nf_out, re.IGNORECASE)
    out["nextflow"] = m.group(1) if m else "unknown"

    bac_out = _run([get_bactopia_bin(), "--version"])
    m = re.search(r"bactopia\s+v?([\d.]+)", bac_out, re.IGNORECASE)
    out["bactopia"] = m.group(1) if m else "unknown"

    # The env's Java is the one Nextflow runs on; the distro's (often older)
    # Java on PATH would be reported as a false negative against the 17+ floor.
    java_out = _run([get_env_bin("java"), "-version"])
    # Capture the whole quoted string: conda JDKs report builds like
    # "23.0.2-internal", which a digits-only pattern silently misses.
    m = re.search(r'version\s+"([^"]+)"', java_out)
    out["java"] = m.group(1) if m else "unknown"

    docker_out = _run(["docker", "--version"])
    m = re.search(r"Docker version\s+([\d.]+)", docker_out, re.IGNORECASE)
    ver = m.group(1) if m else "unknown"
    # Distinguish "installed" from "daemon running" — a stopped daemon breaks runs.
    from bearhub.core.system import docker_running
    if ver == "unknown":
        out["docker"] = "not installed"
    elif docker_running():
        out["docker"] = f"{ver} (running)"
    else:
        out["docker"] = f"{ver} (daemon NOT running)"

    return out
