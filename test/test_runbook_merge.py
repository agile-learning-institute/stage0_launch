from pathlib import Path

import pytest

from stage0_launch.runbook_merge import resolve_merge_volume_paths


def test_resolve_merge_rewrites_when_host_bind_known(monkeypatch, tmp_path):
    lp = Path("/launchpad")
    repo = lp / "proj_r"
    specs = lp / "umbrella" / "Specifications"

    def fake_bind(_root: Path) -> Path | None:
        return tmp_path

    monkeypatch.setattr(
        "stage0_launch.runbook_merge.host_bind_source_for_launchpad_root",
        fake_bind,
    )

    r_repo, r_specs = resolve_merge_volume_paths(repo, specs, lp)
    assert r_repo == tmp_path / "proj_r"
    assert r_specs == tmp_path / "umbrella" / "Specifications"


def test_resolve_merge_passes_through_when_no_host_bind(monkeypatch, tmp_path):
    lp = tmp_path / "launchpad"
    lp.mkdir()
    repo = lp / "clone"
    specs = lp / "specs"
    repo.mkdir()
    specs.mkdir()

    monkeypatch.setattr(
        "stage0_launch.runbook_merge.host_bind_source_for_launchpad_root",
        lambda _root: None,
    )

    r_repo, r_specs = resolve_merge_volume_paths(repo, specs, lp)
    assert r_repo == repo.resolve()
    assert r_specs == specs.resolve()


def test_resolve_merge_raises_when_container_paths_but_no_host_bind(monkeypatch):
    lp = Path("/launchpad")
    repo = lp / "r"
    specs = lp / "mentorhub" / "Specifications"

    monkeypatch.setattr(
        "stage0_launch.runbook_merge.host_bind_source_for_launchpad_root",
        lambda _root: None,
    )

    with pytest.raises(RuntimeError, match="STAGE0_LAUNCHPAD_HOST_PATH"):
        resolve_merge_volume_paths(repo, specs, lp)


def test_resolve_merge_same_for_uppercase_launchpad(monkeypatch, tmp_path):
    lp = Path("/Launchpad")
    repo = lp / "r"
    specs = lp / "u" / "Specifications"

    monkeypatch.setattr(
        "stage0_launch.runbook_merge.host_bind_source_for_launchpad_root",
        lambda _root: tmp_path,
    )

    r_repo, r_specs = resolve_merge_volume_paths(repo, specs, lp)
    assert r_repo == tmp_path / "r"
    assert r_specs == tmp_path / "u" / "Specifications"
