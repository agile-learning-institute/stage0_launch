"""Launchpad stub: marks successful bootstrap and names the umbrella folder."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

STUB_NAME = ".stage0-launch.yaml"

_UMBRELLA_KEY = "umbrella"
_SAFE_FOLDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def stub_path(launchpad: Path) -> Path:
    return launchpad / STUB_NAME


def read_stub_umbrella(launchpad: Path) -> str | None:
    """Return umbrella folder name from stub, or None if missing/invalid."""
    p = stub_path(launchpad)
    if not p.is_file():
        return None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get(_UMBRELLA_KEY)
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    if not name or not _SAFE_FOLDER.match(name):
        return None
    return name


def write_stub(launchpad: Path, umbrella_folder: str) -> None:
    if not _SAFE_FOLDER.match(umbrella_folder.strip()):
        raise ValueError("invalid umbrella folder name for stub")
    stub_path(launchpad).write_text(
        yaml.safe_dump({_UMBRELLA_KEY: umbrella_folder.strip()}, sort_keys=False),
        encoding="utf-8",
    )
