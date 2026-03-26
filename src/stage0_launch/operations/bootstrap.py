from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import TextIO

from stage0_launch.launchpad_stub import write_stub
from stage0_launch.operations.umbrella_ops import (
    UmbrellaContext,
    cmd_launch_all,
    github_token_from_env,
)
from stage0_launch.procutil import run_streaming, sleep_s
from stage0_launch.runbook_merge import run_runbook_merge


def _git_inside(d: Path) -> bool:
    p = subprocess.run(
        ["git", "rev-parse"],
        cwd=str(d),
        capture_output=True,
        text=True,
    )
    return p.returncode == 0


def run_bootstrap(specs_dir: Path, launchpad: Path, log: TextIO) -> None:
    from stage0_launch.yqutil import yq_eval

    token = github_token_from_env()
    if not token:
        raise RuntimeError("GITHUB_TOKEN or GH_TOKEN required")
    if not specs_dir.is_dir() or not (specs_dir / "product.yaml").is_file():
        raise RuntimeError(f"Invalid specifications directory: {specs_dir}")
    if not launchpad.is_dir():
        raise RuntimeError(f"Launchpad is not a directory: {launchpad}")
    if _git_inside(launchpad):
        raise RuntimeError("Launchpad must be outside any git repository")

    org = yq_eval(".organization.git_org", specs_dir / "product.yaml")
    slug = yq_eval(".info.slug", specs_dir / "product.yaml")
    base_port = yq_eval(".info.base_port", specs_dir / "product.yaml")
    if not org or org == "null":
        raise RuntimeError("organization.git_org in product.yaml")
    if not slug or slug == "null":
        raise RuntimeError("info.slug in product.yaml")
    if not base_port or base_port == "null":
        raise RuntimeError("info.base_port in product.yaml")

    umbrella_dir = launchpad / slug
    service_source = launchpad

    log.write("=== 1. Creating umbrella repo ===\n")
    log.flush()
    run_streaming(
        [
            "gh",
            "repo",
            "create",
            f"{org}/{slug}",
            "--template",
            "agile-learning-institute/stage0_template_umbrella",
            "--public",
        ],
        cwd=launchpad,
        log=log,
    )
    sleep_s(5, log)

    log.write("=== 2. Cloning umbrella to launchpad ===\n")
    log.flush()
    clone_url = f"https://x-access-token:{token}@github.com/{org}/{slug}.git"
    run_streaming(["git", "clone", clone_url, slug], cwd=launchpad, log=log)

    log.write("=== 3. Merge specifications ===\n")
    log.flush()
    run_runbook_merge(
        log,
        repo_dir=umbrella_dir,
        specifications_dir=specs_dir,
        launchpad=launchpad,
        service_name=None,
    )

    log.write("=== 4. Copy specifications into umbrella ===\n")
    log.flush()
    dest_specs = umbrella_dir / "Specifications"
    dest_specs.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.yaml", "*.yml"):
        for f in specs_dir.glob(pattern):
            shutil.copy2(f, dest_specs / f.name)

    ctx = UmbrellaContext.load(umbrella_dir, service_source)

    log.write("=== 5. Build and publish umbrella package ===\n")
    log.flush()
    ctx.git_https_setup(log)
    ctx.docker_login(log)
    run_streaming(["make", "build-package"], cwd=umbrella_dir, log=log)
    run_streaming(["make", "publish-package"], cwd=umbrella_dir, log=log)

    log.write("=== 6. Commit and push umbrella ===\n")
    log.flush()
    subprocess.run(
        [
            "git",
            "config",
            "--global",
            f"url.https://x-access-token:{token}@github.com/.insteadOf",
            "https://github.com/",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "stage0-launch@localhost"],
        cwd=str(umbrella_dir),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Stage0 Launch"],
        cwd=str(umbrella_dir),
        capture_output=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(umbrella_dir), check=True)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(umbrella_dir),
    )
    if diff.returncode != 0:
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Merge and specifications; build and publish complete",
            ],
            cwd=str(umbrella_dir),
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(umbrella_dir),
            check=True,
        )

    log.write("=== 7. Launch all services (umbrella + repos) ===\n")
    log.flush()
    cmd_launch_all(ctx, log)

    log.write("\n")
    log.write(f"LAUNCH COMPLETE — umbrella at {umbrella_dir}\n")
    log.write(f"Base port: {base_port}\n")
    log.flush()
    write_stub(launchpad, slug)
    log.write(f"Wrote launchpad stub → umbrella {slug!r}\n")
    log.flush()
