"""Run mypy --strict on annotated files and collect errors."""

from __future__ import annotations

import subprocess
from pathlib import Path


def verify_with_mypy(
    paths: list[Path],
    python_version: str = "3.11",
) -> tuple[bool, list[str]]:
    """Run ``mypy --strict`` on *paths* and return ``(success, errors)``.

    Args:
        paths: List of files or directories to check.
        python_version: Python version string for mypy (e.g. ``"3.11"``).

    Returns:
        A ``(success, errors)`` tuple where *success* is ``True`` when mypy
        exits with code 0 and *errors* is a list of diagnostic lines.
    """
    if not paths:
        return True, []

    cmd = [
        "python",
        "-m",
        "mypy",
        "--strict",
        f"--python-version={python_version}",
        "--no-error-summary",
        "--",
        *[str(p) for p in paths],
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    errors: list[str] = []
    # Collect diagnostics from both stdout and stderr. mypy may emit
    # configuration/usage errors (exit code 2) primarily on stderr.
    for stream in (result.stdout, result.stderr):
        if not stream:
            continue
        for line in stream.splitlines():
            line = line.strip()
            if line and not line.startswith("Success"):
                errors.append(line)

    # mypy exits 0 on success, 1 on type errors, 2 on usage errors
    success = result.returncode == 0
    return success, errors
