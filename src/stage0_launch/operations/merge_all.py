from __future__ import annotations

import shutil
from pathlib import Path
from typing import TextIO

from stage0_launch.architecture_tasks import (
    LaunchRepoTask,
    collect_all_launch_tasks,
    template_repo_basename,
)
from stage0_launch.launchpad_compare import DEPENDENCY_LOCK_BASENAMES
from stage0_launch.launchpad_stub import STUB_NAME, write_stub
from stage0_launch.runbook_merge import run_runbook_merge
from stage0_launch.yqutil import yq_eval

UMBRELLA_TEMPLATE_BASENAME = "stage0_template_umbrella"


def copy_template_tree(src: Path, dest: Path) -> None:
    """Copy template working tree; omit ``.git``."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _ignore_template_copy(_dir: str, names: list[str]) -> set[str]:
        return {
            n
            for n in names
            if n == ".git" or n in DEPENDENCY_LOCK_BASENAMES
        }

    shutil.copytree(src, dest, ignore=_ignore_template_copy)


def copy_spec_yaml_files(source_specs: Path, dest_specs: Path) -> None:
    dest_specs.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.yaml", "*.yml"):
        for f in source_specs.glob(pattern):
            shutil.copy2(f, dest_specs / f.name)


def _validate_template_dirs(
    tasks: list[LaunchRepoTask],
    templates_root: Path,
    umbrella_template: Path,
    *,
    require_umbrella_template: bool,
) -> None:
    if require_umbrella_template:
        if not umbrella_template.is_dir():
            raise RuntimeError(
                f"umbrella template directory not found: {umbrella_template}"
            )
    for task in tasks:
        base = template_repo_basename(task.template)
        if not base:
            continue
        tdir = templates_root / base
        if not tdir.is_dir():
            raise RuntimeError(
                f"template directory not found for {task.template!r}: {tdir}"
            )


def run_merge_all(
    launchpad: Path,
    source_specifications: Path,
    templates_root: Path,
    log: TextIO,
    *,
    skip_umbrella: bool = False,
    emit_launchpad_stub: bool = False,
) -> None:
    """
    Materialize umbrella (unless skipped) and all service repos under ``launchpad``,
    then run runbook merge for each. Service merges use
    ``<launchpad>/<slug>/Specifications`` only (after specs are copied into the umbrella).
    """
    source_specifications = source_specifications.resolve()
    launchpad = launchpad.resolve()
    templates_root = templates_root.resolve()
    launchpad.mkdir(parents=True, exist_ok=True)

    product = source_specifications / "product.yaml"
    arch_src = source_specifications / "architecture.yaml"
    catalog = source_specifications / "catalog.yaml"
    if not product.is_file():
        raise RuntimeError(f"missing {product}")
    if not arch_src.is_file():
        raise RuntimeError(f"missing {arch_src}")
    if not catalog.is_file():
        raise RuntimeError(f"missing {catalog}")

    slug = yq_eval(".info.slug", product)
    if not slug or slug == "null":
        raise RuntimeError("info.slug in product.yaml")

    umbrella_dest = launchpad / slug
    umbrella_template_dir = templates_root / UMBRELLA_TEMPLATE_BASENAME

    if skip_umbrella:
        arch_preflight = umbrella_dest / "Specifications" / "architecture.yaml"
        if not arch_preflight.is_file():
            raise RuntimeError(
                f"--skip-umbrella requires {arch_preflight} (run full merge-all first)"
            )
        tasks_pre = collect_all_launch_tasks(arch_preflight)
        _validate_template_dirs(
            tasks_pre,
            templates_root,
            umbrella_template_dir,
            require_umbrella_template=False,
        )
    else:
        tasks_pre = collect_all_launch_tasks(arch_src)
        _validate_template_dirs(
            tasks_pre,
            templates_root,
            umbrella_template_dir,
            require_umbrella_template=True,
        )

    if not skip_umbrella:
        log.write(
            f"=== Umbrella: copy {umbrella_template_dir.name} → {umbrella_dest}\n"
        )
        log.flush()
        copy_template_tree(umbrella_template_dir, umbrella_dest)
        log.write("=== Umbrella: runbook merge (specifications = source)\n")
        log.flush()
        run_runbook_merge(
            log,
            repo_dir=umbrella_dest,
            specifications_dir=source_specifications,
            launchpad=launchpad,
            service_name=None,
        )
        dest_specs = umbrella_dest / "Specifications"
        log.write(f"=== Copy YAML specs → {dest_specs}\n")
        log.flush()
        copy_spec_yaml_files(source_specifications, dest_specs)
    else:
        specs_in_umbrella = umbrella_dest / "Specifications"
        if not specs_in_umbrella.is_dir():
            raise RuntimeError(f"--skip-umbrella requires {specs_in_umbrella} to exist")

    arch_merged = umbrella_dest / "Specifications" / "architecture.yaml"
    if not arch_merged.is_file():
        raise RuntimeError(f"missing {arch_merged}")
    tasks = collect_all_launch_tasks(arch_merged)

    for task in tasks:
        base = template_repo_basename(task.template)
        src_dir = templates_root / base
        repo_dest = launchpad / f"{slug}_{task.repo_name}"
        log.write(
            f"=== Service {task.svc}/{task.repo_name}: copy {base} → {repo_dest.name}\n"
        )
        log.flush()
        copy_template_tree(src_dir, repo_dest)
        log.write(f"=== Service {task.svc}/{task.repo_name}: runbook merge\n")
        log.flush()
        run_runbook_merge(
            log,
            repo_dir=repo_dest,
            specifications_dir=umbrella_dest / "Specifications",
            launchpad=launchpad,
            service_name=task.svc,
        )

    if emit_launchpad_stub:
        write_stub(launchpad, slug)
        log.write(f"=== Wrote {STUB_NAME} → umbrella {slug!r}\n")
        log.flush()

    log.write("merge-all complete.\n")
    log.flush()
