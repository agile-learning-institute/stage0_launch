from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import TextIO

from stage0_launch.config import CONTAINER_LAUNCHPAD
from stage0_launch.procutil import run_streaming

MERGE_IMAGE = "ghcr.io/agile-learning-institute/stage0_runbook_merge:latest"


def _docker_inspect_bind_source(mount_destination: str) -> Path | None:
    """
    Read ``.Mounts[].Source`` where ``Destination`` equals ``mount_destination`` from
    ``docker inspect``.

    On Docker Desktop, ``findmnt -o SOURCE`` can return a path that is not usable for
    nested ``docker run -v`` (wrong or empty bind). The engine's mount record matches
    what the daemon expects for follow-on binds.
    """
    candidates: list[str] = []
    for key in ("STAGE0_LAUNCH_CONTAINER_NAME", "HOSTNAME"):
        v = os.environ.get(key, "").strip()
        if v:
            candidates.append(v)
    try:
        hn = Path("/etc/hostname").read_text(encoding="utf-8", errors="replace").strip()
        if hn:
            candidates.append(hn)
    except OSError:
        pass
    try:
        cg = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"/docker/([0-9a-f]{64})", cg, re.IGNORECASE):
            candidates.append(m.group(1))
            candidates.append(m.group(1)[:12])
    except OSError:
        pass
    seen: set[str] = set()
    ordered: list[str] = []
    for x in candidates:
        if x and x not in seen:
            seen.add(x)
            ordered.append(x)

    for cid in ordered:
        r = subprocess.run(
            ["docker", "inspect", cid, "--format", "{{json .Mounts}}"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            continue
        try:
            mounts = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        if not isinstance(mounts, list):
            continue
        for m in mounts:
            if not isinstance(m, dict):
                continue
            if m.get("Destination") != mount_destination:
                continue
            src = m.get("Source")
            if isinstance(src, str) and src and not src.startswith("/dev/"):
                return Path(src)
    return None


def _findmnt_json_source(mount_point: Path) -> Path | None:
    try:
        r = subprocess.run(
            ["findmnt", "-J", str(mount_point)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    fss = data.get("filesystems")
    if not isinstance(fss, list) or not fss:
        return None
    first = fss[0]
    if not isinstance(first, dict):
        return None
    src = first.get("source")
    if isinstance(src, str) and src and not src.startswith("/dev/"):
        return Path(src)
    return None


def _findmnt_plain_source(mount_point: Path) -> Path | None:
    try:
        r = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", str(mount_point)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if r.returncode != 0:
        return None
    src = r.stdout.strip()
    if not src or src.startswith("/dev/"):
        return None
    return Path(src)


def host_bind_source_for_launchpad_root(launchpad_root: Path) -> Path | None:
    """
    Path the **host** Docker daemon should use for the directory bound at ``launchpad_root``
    inside the launch environment.

    Resolution order:

    1. ``STAGE0_LAUNCHPAD_HOST_PATH`` — absolute host path (most reliable when set).
    2. ``docker inspect`` — bind source for ``launchpad_root`` as the mount destination
       (e.g. ``/Launchpad`` or ``/launchpad`` when ``LAUNCHPAD_DIR`` overrides the in-container path).
    3. ``findmnt`` — fallback on Linux when inspect is unavailable.

    Set ``STAGE0_LAUNCH_CONTAINER_NAME`` (compose sets this to match ``container_name``) so
    inspect works even when ``HOSTNAME`` is not the container id.
    """
    override = os.environ.get("STAGE0_LAUNCHPAD_HOST_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    dest = str(launchpad_root.resolve())
    src = _docker_inspect_bind_source(dest)
    if src is not None:
        return src

    src = _findmnt_json_source(launchpad_root)
    if src is not None:
        return src

    return _findmnt_plain_source(launchpad_root)


def host_launchpad_bind_source() -> Path | None:
    """Backward-compatible alias for ``/Launchpad`` as the in-container mount."""
    return host_bind_source_for_launchpad_root(CONTAINER_LAUNCHPAD)


def _paths_under_launchpad(
    repo_r: Path, specs_r: Path, lp: Path
) -> tuple[Path, Path]:
    try:
        rel_repo = repo_r.relative_to(lp)
        rel_specs = specs_r.relative_to(lp)
    except ValueError as e:
        raise RuntimeError(
            "Repo and specifications paths must lie under the launchpad directory "
            f"({lp}) when resolving merge bind mounts."
        ) from e
    return rel_repo, rel_specs


def resolve_merge_volume_paths(
    repo_dir: Path,
    specifications_dir: Path,
    launchpad: Path,
) -> tuple[Path, Path]:
    """
    Return ``(repo_src, specifications_src)`` for ``docker -v`` as seen by the daemon.

    When the launchpad root is a bind mount inside the launch container (``/Launchpad``,
    ``/launchpad``, or ``LAUNCHPAD_DIR``), paths under it must be rewritten to the host
    bind source so nested ``docker run`` works (Docker-outside-of-Docker).
    """
    lp = launchpad.resolve()
    repo_r = repo_dir.resolve()
    specs_r = specifications_dir.resolve()
    host_root = host_bind_source_for_launchpad_root(lp)
    if host_root is not None:
        rel_repo, rel_specs = _paths_under_launchpad(repo_r, specs_r, lp)
        return host_root / rel_repo, host_root / rel_specs

    for p in (repo_r, specs_r):
        ps = str(p)
        if ps.startswith("/Launchpad/") or ps.startswith("/launchpad/"):
            raise RuntimeError(
                "Cannot resolve the host launchpad path for merge (nested docker bind mounts "
                "must use paths the host daemon knows). Set STAGE0_LAUNCHPAD_HOST_PATH to your "
                "host launchpad directory, or ensure the launchpad bind mount is visible to "
                "docker inspect / findmnt."
            )
    return repo_r, specs_r


def run_runbook_merge(
    log: TextIO,
    *,
    repo_dir: Path,
    specifications_dir: Path,
    launchpad: Path,
    service_name: str | None = None,
    line_prefix: str = "",
) -> None:
    """
    Run the stage0_runbook_merge image with explicit volume mounts.

    ``service_name`` is passed as ``SERVICE_NAME`` for templates that scope merge by domain
    (e.g. flask_mongo, vue_vuetify). Omit for umbrella / templates that do not use it.
    """
    repo_src, specs_src = resolve_merge_volume_paths(
        repo_dir, specifications_dir, launchpad
    )
    extra = f", SERVICE_NAME={service_name!r}" if service_name is not None else ""
    log.write(
        f"{line_prefix}(merge: docker bind repo={repo_src} specifications={specs_src}"
        f"{extra})\n"
    )
    log.flush()
    lvl = os.environ.get("LOG_LEVEL", "INFO")
    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{repo_src}:/repo",
        "-v",
        f"{specs_src}:/specifications",
        "-e",
        f"LOG_LEVEL={lvl}",
    ]
    if service_name is not None:
        cmd.extend(["-e", f"SERVICE_NAME={service_name}"])
    cmd.append(MERGE_IMAGE)
    run_streaming(cmd, log=log, line_prefix=line_prefix)
