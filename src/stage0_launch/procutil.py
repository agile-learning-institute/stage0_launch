from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO


def run_streaming(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    log: TextIO,
    line_prefix: str = "",
) -> None:
    display = " ".join(cmd)
    pfx = line_prefix or ""

    def emit(msg: str) -> None:
        log.write(msg)
        log.flush()

    emit(f"{pfx}$ {display}\n")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    with subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            emit(f"{pfx}{line}")
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed ({proc.returncode}): {display}")


def run_streaming_with_one_retry(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    log: TextIO,
    line_prefix: str = "",
    pause_s: float = 3.0,
    retry_note: str = "retrying once after a short pause",
) -> None:
    """
    Run ``run_streaming``; on ``RuntimeError`` (non-zero exit), log, wait, then run again once.
    Used for network-sensitive steps such as ``publish-package``.
    """
    pfx = line_prefix or ""
    try:
        run_streaming(cmd, cwd=cwd, env=env, log=log, line_prefix=line_prefix)
    except RuntimeError as exc:
        display = " ".join(cmd)
        log.write(
            f"{pfx}Command failed ({exc}); {retry_note} ({pause_s:g}s)…\n"
        )
        log.flush()
        time.sleep(pause_s)
        run_streaming(cmd, cwd=cwd, env=env, log=log, line_prefix=line_prefix)


def run_git_clone_streaming_with_one_retry(
    clone_url: str,
    dest_name: str,
    *,
    cwd: Path,
    log: TextIO,
    line_prefix: str = "",
    pause_s: float = 3.0,
    retry_note: str = "retrying clone once after a short pause",
) -> None:
    """Clone after ``wait_for_git_remote_refs``; retry once on failure.

    Removes a partially-created destination directory before retry so the second
    ``git clone`` is not blocked by a non-empty folder.
    """

    def attempt() -> None:
        run_streaming(
            ["git", "clone", clone_url, dest_name],
            cwd=cwd,
            log=log,
            line_prefix=line_prefix,
        )

    pfx = line_prefix or ""
    dest = cwd / dest_name
    try:
        attempt()
    except RuntimeError as exc:
        display = f"git clone … {dest_name}"
        log.write(
            f"{pfx}Command failed ({exc}); {retry_note} ({pause_s:g}s)…\n"
        )
        log.flush()
        if dest.exists():
            shutil.rmtree(dest)
        time.sleep(pause_s)
        attempt()


def sleep_s(seconds: float, log: TextIO, *, line_prefix: str = "") -> None:
    pfx = line_prefix or ""
    log.write(f"{pfx}(sleep {seconds}s)\n")
    log.flush()
    time.sleep(seconds)


def wait_for_git_remote_refs(
    clone_url: str,
    log: TextIO,
    *,
    line_prefix: str = "",
    timeout_s: float = 180.0,
    interval_s: float = 3.0,
) -> None:
    """Block until ``git ls-remote`` reports at least one ref (repo is non-empty).

    After ``gh repo create --template …``, GitHub may lag before the remote is
    visible (``ls-remote`` can return “Repository not found” or empty refs while
    the API and storage catch up). Poll until success or ``timeout_s``.

    A successful ``ls-remote`` with no refs yet means the template copy has
    not produced an initial commit; that is retried the same way.
    """
    deadline = time.time() + timeout_s
    pfx = line_prefix or ""
    safe_url = clone_url
    if "x-access-token:" in safe_url:
        safe_url = urllib.parse.urlunparse(
            urllib.parse.urlparse(clone_url)._replace(netloc="github.com")
        )
    attempt = 0
    last_detail = ""
    while True:
        attempt += 1
        r = subprocess.run(
            ["git", "ls-remote", clone_url],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return

        if r.returncode != 0:
            detail = (r.stderr or r.stdout).strip() or "no output"
            one_line = " ".join(detail.split())
            if len(one_line) > 160:
                one_line = one_line[:157] + "…"
            last_detail = f"ls-remote exit {r.returncode}: {one_line}"
        else:
            last_detail = "remote has no refs yet (template copy may still be running)"

        if time.time() >= deadline:
            raise RuntimeError(
                f"Timed out after {timeout_s}s waiting for remote to be ready "
                f"({attempt} attempts): {safe_url}\n"
                f"Last status: {last_detail}"
            )
        log.write(
            f"{pfx}(waiting for remote, attempt {attempt}, next in {interval_s}s — "
            f"{last_detail})\n"
        )
        log.flush()
        time.sleep(interval_s)
