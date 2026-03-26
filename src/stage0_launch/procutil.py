from __future__ import annotations

import os
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

    After ``gh repo create --template …``, GitHub may take time to copy the
    template and create the initial commit; cloning immediately yields an empty
    working tree and breaks downstream steps (e.g. missing ``.stage0_template/process.yaml``).
    """
    deadline = time.time() + timeout_s
    pfx = line_prefix or ""
    safe_url = clone_url
    if "x-access-token:" in safe_url:
        safe_url = urllib.parse.urlunparse(
            urllib.parse.urlparse(clone_url)._replace(netloc="github.com")
        )
    attempt = 0
    while True:
        attempt += 1
        r = subprocess.run(
            ["git", "ls-remote", clone_url],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"git ls-remote failed ({r.returncode}): "
                f"{(r.stderr or r.stdout).strip() or 'no output'}"
            )
        if r.stdout.strip():
            return
        if time.time() >= deadline:
            raise RuntimeError(
                f"Timed out after {timeout_s}s waiting for remote to have commits "
                f"({attempt} attempts): {safe_url}"
            )
        log.write(
            f"{pfx}(waiting for GitHub template copy to finish, "
            f"attempt {attempt}, next in {interval_s}s)…\n"
        )
        log.flush()
        time.sleep(interval_s)
