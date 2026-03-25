from __future__ import annotations

import os
from pathlib import Path

# Default mount path inside the container (compose maps the host folder here).
CONTAINER_LAUNCHPAD = Path("/Launchpad")


def launchpad_dir() -> Path:
    """
    Resolve the launchpad root.

    ``LAUNCHPAD_DIR`` overrides everything (tests, custom mounts).
    Otherwise, if ``/Launchpad`` exists (typical in Docker), use it; else current directory.
    """
    env = os.environ.get("LAUNCHPAD_DIR", "").strip()
    if env:
        return Path(env).resolve()
    if CONTAINER_LAUNCHPAD.is_dir():
        return CONTAINER_LAUNCHPAD.resolve()
    return Path(".").resolve()
