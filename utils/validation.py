"""
Input validation helpers for BEAR-HUB.

Centralizes path sanitization to prevent shell injection via user-supplied
paths that are passed to subprocess commands.
"""

import re
import pathlib

# Characters that could break out of a quoted shell argument or act as operators
_DANGEROUS = re.compile(r'[;&|`$<>!()\[\]{}\\]')


def validate_path(p: str) -> tuple[bool, str]:
    """
    Validate a filesystem path supplied by the user.

    Checks for shell metacharacters that could cause injection when the path
    is interpolated into a shell command string, then resolves the path.

    Args:
        p: The raw path string from user input.

    Returns:
        (True, resolved_path_str)  on success.
        (False, error_message)     on failure.
    """
    if not p or not p.strip():
        return False, "Path must not be empty."

    if _DANGEROUS.search(p):
        bad = ", ".join(sorted({c for c in p if _DANGEROUS.match(c)}))
        return False, f"Path contains invalid character(s): {bad!r}"

    try:
        resolved = str(pathlib.Path(p).expanduser().resolve())
        return True, resolved
    except Exception as e:
        return False, f"Cannot resolve path: {e}"


def validate_outdir(outdir: str) -> tuple[bool, str]:
    """
    Validate an output directory path.

    Same as validate_path but additionally ensures the path string is not
    suspiciously short (e.g. bare "/" or ".").

    Returns:
        (True, resolved_path_str) or (False, error_message).
    """
    ok, result = validate_path(outdir)
    if not ok:
        return False, result
    if len(result) < 3:
        return False, f"Output directory path is too short: {result!r}"
    return True, result
