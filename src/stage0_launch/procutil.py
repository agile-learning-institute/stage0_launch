from __future__ import annotations

import os
import subprocess
import time
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
