"""Detect installed tool versions for the Status page."""
from __future__ import annotations

import re
import subprocess

from bearhub.core.system import get_nextflow_bin, which


def _run(args: list[str]) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


def get_versions() -> dict[str, str]:
    out: dict[str, str] = {}

    nf = get_nextflow_bin()
    nf_out = _run([nf, "-version"])
    m = re.search(r"version\s+([\d.]+(?:\.[\w]+)?)", nf_out, re.IGNORECASE)
    out["nextflow"] = m.group(1) if m else "unknown"

    bac_bin = which("bactopia") or "bactopia"
    bac_out = _run([bac_bin, "--version"])
    m = re.search(r"bactopia\s+v?([\d.]+)", bac_out, re.IGNORECASE)
    out["bactopia"] = m.group(1) if m else "unknown"

    java_out = _run(["java", "-version"])
    m = re.search(r'version\s+"([\d._]+)"', java_out)
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
