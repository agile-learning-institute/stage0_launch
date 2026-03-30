from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LaunchRepoTask:
    svc: str
    repo_name: str
    template: str
    publish: str


def template_repo_basename(template_ref: str) -> str:
    """``org/stage0_template_foo`` → ``stage0_template_foo``."""
    t = (template_ref or "").strip()
    if not t or t == "null":
        return ""
    return t.split("/")[-1]


def domain_names_from_architecture(arch_file: Path) -> list[str]:
    raw = subprocess.run(
        ["yq", "-r", ".architecture.domains[].name", str(arch_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ln.strip() for ln in raw.stdout.splitlines() if ln.strip()]


def repo_lines_for_arch_domain(arch_file: Path, svc: str) -> list[tuple[str, str, str]]:
    """Return (repo_name, template, publish) for api/spa repos in domain ``svc``."""
    q = (
        f'.architecture.domains[] | select(.name == "{svc}") | .repos[] '
        f'| select(.type == "api" or .type == "spa") '
        f'| (.name + "|" + .template + "|" + (.publish // ""))'
    )
    r = subprocess.run(
        ["yq", "-r", q, str(arch_file)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return []
    out: list[tuple[str, str, str]] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or line == "null":
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            name = parts[0]
            template = parts[1] if len(parts) > 1 else ""
            publish = parts[2] if len(parts) > 2 else ""
            out.append((name, template, publish))
    return out


def collect_all_launch_tasks(arch_file: Path) -> list[LaunchRepoTask]:
    """
    All launch merge tasks in architecture domain order, with null/empty template
    rows skipped (e.g. ``spa_ref`` without a template).
    """
    tasks: list[LaunchRepoTask] = []
    for svc in domain_names_from_architecture(arch_file):
        for repo_name, template, publish in repo_lines_for_arch_domain(arch_file, svc):
            if not repo_name:
                continue
            base = template_repo_basename(template)
            if not base:
                continue
            tasks.append(LaunchRepoTask(svc, repo_name, template, publish))
    return tasks


def collect_launch_tasks_for_services(
    arch_file: Path, services_list: str
) -> list[LaunchRepoTask]:
    """Preserve ``services_list`` order (space-separated domain names)."""
    order = [s.strip() for s in services_list.split() if s.strip()]
    if not order:
        return []
    wanted = set(order)
    by_svc: dict[str, list[LaunchRepoTask]] = {svc: [] for svc in order}
    for task in collect_all_launch_tasks(arch_file):
        if task.svc in wanted:
            by_svc.setdefault(task.svc, []).append(task)
    out: list[LaunchRepoTask] = []
    for svc in order:
        out.extend(by_svc.get(svc, []))
    return out
