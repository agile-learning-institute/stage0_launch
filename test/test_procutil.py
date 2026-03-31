"""Tests for process streaming helpers."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from stage0_launch.procutil import run_streaming_with_one_retry


def test_run_streaming_with_one_retry_runs_twice_on_first_failure(monkeypatch):
    log = StringIO()
    calls: list[int] = []

    def fake_run_streaming(cmd, **kwargs) -> None:
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("transient")

    monkeypatch.setattr(
        "stage0_launch.procutil.run_streaming", fake_run_streaming
    )
    monkeypatch.setattr("stage0_launch.procutil.time.sleep", lambda s: None)

    run_streaming_with_one_retry(
        ["make", "publish-package"],
        cwd=Path("."),
        log=log,
    )

    assert len(calls) == 2


def test_run_streaming_with_one_retry_propagates_if_both_fail(monkeypatch):
    log = StringIO()

    def fake_run_streaming(cmd, **kwargs) -> None:
        raise RuntimeError("still bad")

    monkeypatch.setattr(
        "stage0_launch.procutil.run_streaming", fake_run_streaming
    )
    monkeypatch.setattr("stage0_launch.procutil.time.sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="still bad"):
        run_streaming_with_one_retry(
            ["make", "publish-package"],
            cwd=Path("."),
            log=log,
        )


def test_run_streaming_with_one_retry_single_call_on_success(monkeypatch):
    log = StringIO()
    calls = 0

    def fake_run_streaming(cmd, **kwargs) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        "stage0_launch.procutil.run_streaming", fake_run_streaming
    )

    run_streaming_with_one_retry(
        ["make", "publish-package"],
        cwd=Path("."),
        log=log,
    )

    assert calls == 1
