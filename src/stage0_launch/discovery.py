from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from stage0_launch.launchpad_stub import read_stub_umbrella, stub_path
from stage0_launch.yqutil import yq_eval


@dataclass
class DiscoveryResult:
    """Interactive mode when ``.stage0-launch.yaml`` exists and points at a valid umbrella."""

    ok: bool
    specs_dir: Path | None
    slug: str | None
    error: str | None


def _has_three_yaml(d: Path) -> bool:
    return (
        (d / "product.yaml").is_file()
        and (d / "architecture.yaml").is_file()
        and (d / "catalog.yaml").is_file()
    )


def launchpad_specs_complete(d: Path) -> bool:
    """True if directory contains product, architecture, and catalog YAML."""
    return _has_three_yaml(d)


def _launchpad_inside_git(lp: Path) -> bool:
    try:
        if not shutil.which("git"):
            return False
        p = subprocess.run(
            ["git", "rev-parse"],
            cwd=str(lp),
            capture_output=True,
            text=True,
        )
        return p.returncode == 0
    except OSError:
        return False


def discover(launchpad: Path) -> DiscoveryResult:
    """
    Bootstrap mode: no ``.stage0-launch.yaml`` on the launchpad.

    Interactive mode: stub names a child folder (umbrella); that folder must contain
    ``Specifications`` with the three YAML files and ``info.slug`` matching the folder name.
    """
    if not launchpad.is_dir():
        return DiscoveryResult(False, None, None, "Launchpad is not a directory")
    if _launchpad_inside_git(launchpad):
        return DiscoveryResult(
            False,
            None,
            None,
            "Launchpad must be outside any git repository",
        )

    if not stub_path(launchpad).is_file():
        return DiscoveryResult(False, None, None, None)

    umbrella_name = read_stub_umbrella(launchpad)
    if umbrella_name is None:
        return DiscoveryResult(
            False,
            None,
            None,
            "Invalid .stage0-launch.yaml (expected: umbrella: <folder_name>)",
        )

    umb = launchpad / umbrella_name
    specs = umb / "Specifications"
    if not specs.is_dir() or not _has_three_yaml(specs):
        return DiscoveryResult(
            False,
            None,
            None,
            f"Stub points to {umbrella_name!r} but Specifications are missing or incomplete",
        )

    try:
        slug = yq_eval(".info.slug", specs / "product.yaml")
    except Exception as e:
        return DiscoveryResult(False, None, None, f"Read product.yaml: {e}")
    if not slug or slug == "null":
        return DiscoveryResult(False, None, None, "info.slug missing in product.yaml")
    if umb.name != slug:
        return DiscoveryResult(
            False,
            None,
            None,
            f"Folder name {umb.name!r} must match info.slug {slug!r}",
        )

    return DiscoveryResult(True, specs.resolve(), slug, None)
