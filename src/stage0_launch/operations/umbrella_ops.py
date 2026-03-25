from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from stage0_launch.procutil import run_streaming, sleep_s
from stage0_launch.yqutil import yq_eval


@dataclass
class UmbrellaContext:
    umbrella_dir: Path
    service_source_dir: Path
    root: Path
    specs_dir: Path
    arch_file: Path
    product_file: Path
    slug: str
    org: str
    docker_host: str
    all_services: str

    @classmethod
    def load(cls, umbrella_dir: Path, service_source_dir: Path) -> UmbrellaContext:
        root = umbrella_dir
        specs = root / "Specifications"
        arch = specs / "architecture.yaml"
        product = specs / "product.yaml"
        if not product.is_file():
            raise RuntimeError(f"missing {product}")
        if not arch.is_file():
            raise RuntimeError(f"missing {arch}")
        slug = yq_eval(".info.slug", product)
        org = yq_eval(".organization.git_org", product)
        docker_host = yq_eval(".organization.docker_host", product)
        if not slug or slug == "null":
            raise RuntimeError("info.slug in product.yaml")
        if not org or org == "null":
            raise RuntimeError("organization.git_org in product.yaml")
        if not docker_host or docker_host == "null":
            raise RuntimeError("organization.docker_host in product.yaml")
        raw = subprocess.run(
            ["yq", "-r", ".architecture.domains[].name", str(arch)],
            capture_output=True,
            text=True,
            check=True,
        )
        names = [ln.strip() for ln in raw.stdout.splitlines() if ln.strip()]
        all_services = " ".join(names)
        return cls(
            umbrella_dir=umbrella_dir,
            service_source_dir=service_source_dir,
            root=root,
            specs_dir=specs,
            arch_file=arch,
            product_file=product,
            slug=slug,
            org=org,
            docker_host=docker_host,
            all_services=all_services,
        )

    def git_https_setup(self, log: TextIO) -> None:
        subprocess.run(
            [
                "git",
                "config",
                "--global",
                "--unset-all",
                "url.https://@github.com/.insteadOf",
            ],
            capture_output=True,
            text=True,
        )
        token = os.environ.get("GITHUB_TOKEN", "")
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
        log.write("  git HTTPS insteadOf configured\n")
        log.flush()

    def docker_login(self, log: TextIO) -> None:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise RuntimeError("GITHUB_TOKEN required for docker login")
        registry = self.docker_host.replace("https://", "").split("/")[0]
        if registry == "ghcr.io":
            user = os.environ.get("GH_USERNAME") or os.environ.get(
                "GITHUB_USERNAME", ""
            )
            if not user:
                gh_r = subprocess.run(
                    ["gh", "api", "user", "--jq", ".login"],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "GH_TOKEN": token},
                )
                if gh_r.returncode == 0 and gh_r.stdout.strip():
                    user = gh_r.stdout.strip()
            if not user:
                curl_r = subprocess.run(
                    [
                        "curl",
                        "-sf",
                        "-H",
                        f"Authorization: Bearer {token}",
                        "https://api.github.com/user",
                    ],
                    capture_output=True,
                    text=True,
                )
                if curl_r.returncode == 0:
                    try:
                        user = json.loads(curl_r.stdout).get("login") or ""
                    except json.JSONDecodeError:
                        user = ""
            if not user or user == "null":
                raise RuntimeError(
                    "GHCR login needs your personal GitHub username (GH_USERNAME) "
                    "or token with user API access."
                )
            log.write(f"Logging in to ghcr.io as {user}...\n")
            log.flush()
            p = subprocess.Popen(
                ["docker", "login", "ghcr.io", "-u", user, "--password-stdin"],
                stdin=subprocess.PIPE,
                text=True,
            )
            p.communicate(input=token)
            if p.returncode != 0:
                raise RuntimeError("docker login ghcr.io failed")
        else:
            log.write(f"Logging in to {registry} as {self.org}...\n")
            log.flush()
            p = subprocess.Popen(
                ["docker", "login", registry, "-u", self.org, "--password-stdin"],
                stdin=subprocess.PIPE,
                text=True,
            )
            p.communicate(input=token)
            if p.returncode != 0:
                raise RuntimeError(f"docker login {registry} failed")


def _repo_lines_for_domain(
    ctx: UmbrellaContext, svc: str
) -> list[tuple[str, str, str]]:
    q = (
        f'.architecture.domains[] | select(.name == "{svc}") | .repos[] '
        f'| select(.type == "api" or .type == "spa") '
        f'| (.name + "|" + .template + "|" + (.publish // ""))'
    )
    r = subprocess.run(
        ["yq", "-r", q, str(ctx.arch_file)],
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


def _repo_lines_clone(ctx: UmbrellaContext, svc: str) -> list[tuple[str, str]]:
    q = (
        f'.architecture.domains[] | select(.name == "{svc}") | .repos[] '
        f'| select(.type == "api" or .type == "spa") '
        f'| (.name + "|" + (.publish // ""))'
    )
    r = subprocess.run(
        ["yq", "-r", q, str(ctx.arch_file)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return []
    out: list[tuple[str, str]] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 1)
        name = parts[0]
        publish = parts[1] if len(parts) > 1 else ""
        out.append((name, publish))
    return out


@dataclass(frozen=True)
class _LaunchRepoTask:
    svc: str
    repo_name: str
    template: str
    publish: str


def _collect_launch_tasks(
    ctx: UmbrellaContext, services_list: str
) -> list[_LaunchRepoTask]:
    tasks: list[_LaunchRepoTask] = []
    for svc in services_list.split():
        if not svc:
            continue
        lines = _repo_lines_for_domain(ctx, svc)
        if not lines:
            continue
        for repo_name, template, publish in lines:
            if not repo_name:
                continue
            tasks.append(_LaunchRepoTask(svc, repo_name, template, publish))
    return tasks


def _launch_one_repo(
    ctx: UmbrellaContext,
    token: str,
    source: Path,
    task: _LaunchRepoTask,
    log: TextIO,
    line_prefix: str,
) -> None:
    svc = task.svc
    repo_name = task.repo_name
    template = task.template
    publish = task.publish
    repo_full = f"{ctx.slug}_{repo_name}"
    repo = f"{ctx.org}/{repo_full}"

    def banner(msg: str) -> None:
        log.write(f"{line_prefix}{msg}\n")
        log.flush()

    banner(f"\n### Starting Repo {repo_full}")
    if (source / repo_full).exists():
        shutil.rmtree(source / repo_full)
    run_streaming(
        ["gh", "repo", "create", repo, "--template", template, "--public"],
        cwd=source,
        log=log,
        line_prefix=line_prefix,
    )
    sleep_s(5, log, line_prefix=line_prefix)
    run_streaming(
        [
            "git",
            "clone",
            f"https://x-access-token:{token}@github.com/{repo}.git",
            repo_full,
        ],
        cwd=source,
        log=log,
        line_prefix=line_prefix,
    )
    repo_path = source / repo_full
    env = os.environ.copy()
    env["SERVICE_NAME"] = svc
    banner(f"  Merging {repo_full}")
    run_streaming(
        ["make", "merge", str(ctx.specs_dir)],
        cwd=repo_path,
        env=env,
        log=log,
        line_prefix=line_prefix,
    )
    if publish:
        banner(f"  Build-package & publish-package {repo_full} ({publish})")
        if publish == "make":
            run_streaming(
                ["make", "build-package"],
                cwd=repo_path,
                log=log,
                line_prefix=line_prefix,
            )
            run_streaming(
                ["make", "publish-package"],
                cwd=repo_path,
                log=log,
                line_prefix=line_prefix,
            )
        elif publish == "npm":
            run_streaming(
                ["npm", "run", "build-package"],
                cwd=repo_path,
                log=log,
                line_prefix=line_prefix,
            )
            run_streaming(
                ["npm", "run", "publish-package"],
                cwd=repo_path,
                log=log,
                line_prefix=line_prefix,
            )
        elif publish == "pipenv":
            run_streaming(
                ["pipenv", "run", "build-package"],
                cwd=repo_path,
                log=log,
                line_prefix=line_prefix,
            )
            run_streaming(
                ["pipenv", "run", "publish-package"],
                cwd=repo_path,
                log=log,
                line_prefix=line_prefix,
            )
        else:
            raise RuntimeError(f"Unknown publish: {publish}")
    run_streaming(
        ["git", "add", "-A"],
        cwd=repo_path,
        log=log,
        line_prefix=line_prefix,
    )
    run_streaming(
        ["git", "commit", "-m", "Template Merge Processing Complete"],
        cwd=repo_path,
        log=log,
        line_prefix=line_prefix,
    )
    run_streaming(
        ["git", "push", "origin", "main"],
        cwd=repo_path,
        log=log,
        line_prefix=line_prefix,
    )
    banner(f"### Repo {repo_full} Shipped")


def _emit_repo_failure(
    log: TextIO,
    line_prefix: str,
    repo_full: str,
    svc: str,
    exc: Exception,
) -> None:
    lines = [
        "",
        f"{line_prefix}{'!' * 3} REPO FAILED: {repo_full} (domain/service: {svc}) {'!' * 3}",
        f"{line_prefix}    {type(exc).__name__}: {exc}",
        f"{line_prefix}{'!' * 3} (other repos continue) {'!' * 3}",
        "",
    ]
    log.write("\n".join(lines))
    log.flush()


def _safe_launch_one_repo(
    ctx: UmbrellaContext,
    token: str,
    source: Path,
    task: _LaunchRepoTask,
    log: TextIO,
    line_prefix: str,
) -> tuple[str, str, Exception] | None:
    repo_full = f"{ctx.slug}_{task.repo_name}"
    try:
        _launch_one_repo(ctx, token, source, task, log, line_prefix)
        return None
    except Exception as exc:
        _emit_repo_failure(log, line_prefix, repo_full, task.svc, exc)
        return (repo_full, task.svc, exc)


def _summarize_launch_failures(
    log: TextIO, failures: list[tuple[str, str, Exception]]
) -> None:
    if not failures:
        return
    log.write("\n")
    log.write("=" * 72 + "\n")
    log.write(
        f"!!! LAUNCH FINISHED WITH {len(failures)} REPO FAILURE(S) — SEE ABOVE FOR DETAILS\n"
    )
    for repo_full, svc, exc in failures:
        log.write(
            f"  !!! FAILED: repo={repo_full}  domain={svc}  ({type(exc).__name__}: {exc})\n"
        )
    log.write("=" * 72 + "\n")
    log.flush()


def umbrella_launch_services(
    ctx: UmbrellaContext, services_list: str, log: TextIO
) -> None:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN required")
    log.write("Configuring git and docker for push...\n")
    log.flush()
    ctx.docker_login(log)
    ctx.git_https_setup(log)
    source = ctx.service_source_dir

    tasks = _collect_launch_tasks(ctx, services_list)
    failures: list[tuple[str, str, Exception]] = []
    prev_svc: str | None = None
    for task in tasks:
        if task.svc != prev_svc:
            log.write(f"--- Domain: {task.svc} ---\n")
            log.flush()
            prev_svc = task.svc
        err = _safe_launch_one_repo(ctx, token, source, task, log, "")
        if err:
            failures.append(err)

    _summarize_launch_failures(log, failures)
    log.write("Launch complete.\n")
    log.flush()
    if failures:
        names = ", ".join(r for r, _s, _e in failures)
        raise RuntimeError(f"{len(failures)} repo(s) failed after all attempts: {names}")


def umbrella_clone_services(
    ctx: UmbrellaContext, services_list: str, log: TextIO
) -> None:
    ctx.git_https_setup(log)
    source = ctx.service_source_dir
    for svc in services_list.split():
        if not svc:
            continue
        lines = _repo_lines_clone(ctx, svc)
        if not lines:
            continue
        log.write(f"--- Domain: {svc} ---\n")
        for repo_name, publish in lines:
            if not repo_name:
                continue
            repo_full = f"{ctx.slug}_{repo_name}"
            repo = f"{ctx.org}/{repo_full}"
            if (source / repo_full).exists():
                shutil.rmtree(source / repo_full)
            log.write(f"  Clone {repo}\n")
            log.flush()
            subprocess.run(
                ["git", "clone", f"https://github.com/{repo}.git", repo_full],
                cwd=str(source),
                check=True,
            )
            repo_path = source / repo_full
            log.write(f"  Build {repo_full} ({publish})\n")
            log.flush()
            try:
                if publish == "make":
                    subprocess.run(
                        ["make", "build-package"], cwd=str(repo_path), check=False
                    )
                elif publish == "npm":
                    subprocess.run(
                        ["npm", "run", "build-package"],
                        cwd=str(repo_path),
                        check=False,
                    )
                elif publish == "pipenv":
                    subprocess.run(
                        ["pipenv", "run", "build-package"],
                        cwd=str(repo_path),
                        check=False,
                    )
            except OSError:
                pass
    log.write("clone complete.\n")
    log.flush()


def umbrella_delete_services_only(
    ctx: UmbrellaContext, services_list: str, log: TextIO
) -> None:
    source = ctx.service_source_dir
    for svc in services_list.split():
        if not svc:
            continue
        lines = _repo_lines_clone(ctx, svc)
        if not lines:
            continue
        log.write(f"--- Domain: {svc} ---\n")
        for repo_name, publish in lines:
            if not repo_name:
                continue
            repo_full = f"{ctx.slug}_{repo_name}"
            repo = f"{ctx.org}/{repo_full}"
            local = source / repo_full
            if local.is_dir() and publish:
                log.write(f"  Delete-package {repo_full} ({publish})\n")
                if publish == "make":
                    subprocess.run(
                        ["make", "delete-package"],
                        cwd=str(local),
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
                elif publish == "npm":
                    subprocess.run(
                        ["npm", "run", "delete-package"],
                        cwd=str(local),
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
                elif publish == "pipenv":
                    subprocess.run(
                        ["pipenv", "run", "delete-package"],
                        cwd=str(local),
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
            subprocess.run(
                ["gh", "repo", "delete", repo, "--yes"],
                capture_output=True,
                text=True,
            )
            if local.is_dir():
                shutil.rmtree(local)
    log.write("Delete services complete.\n")
    log.flush()


def cmd_launch_all(ctx: UmbrellaContext, log: TextIO) -> None:
    if not os.environ.get("GITHUB_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN required")
    log.write("Configuring git and docker for push...\n")
    log.flush()
    ctx.git_https_setup(log)
    ctx.docker_login(log)
    start = int(time.time())
    run_streaming(["make", "build-package"], cwd=ctx.root, log=log)
    run_streaming(["make", "publish-package"], cwd=ctx.root, log=log)
    umbrella_launch_services(ctx, ctx.all_services, log)
    end = int(time.time())
    log.write(
        f"Launch Completed - Started at {start} To {end} Duration: {end - start} Seconds\n"
    )
    log.flush()


def cmd_launch_services(ctx: UmbrellaContext, services: str, log: TextIO) -> None:
    umbrella_launch_services(ctx, services, log)


def cmd_clone_services(ctx: UmbrellaContext, services: str, log: TextIO) -> None:
    umbrella_clone_services(ctx, services, log)


def confirm_delete_services(
    ctx: UmbrellaContext,
    i_confirm: str | None,
    i_slug: str | None,
    _log: TextIO,
) -> None:
    if (i_confirm or "").lower() == "yes" and i_slug == ctx.slug:
        return
    raise RuntimeError(
        "Delete services requires I_CONFIRM_DELETE_SERVICES=yes and I_CONFIRM_SLUG matching product slug."
    )


def cmd_delete_services(
    ctx: UmbrellaContext,
    services: str,
    i_confirm: str | None,
    i_slug: str | None,
    log: TextIO,
) -> None:
    confirm_delete_services(ctx, i_confirm, i_slug, log)
    umbrella_delete_services_only(ctx, services, log)
