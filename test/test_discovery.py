from pathlib import Path

from stage0_launch.discovery import discover
from stage0_launch.launchpad_stub import stub_path, write_stub

from test.specs_minimal import write_three_specs


def _write_minimal_specs(spec_dir: Path) -> None:
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "product.yaml").write_text(
        "info:\n  slug: myslug\norganization:\n  git_org: org\n  docker_host: ghcr.io\n"
        "  git_host: https://github.com\n  docker_org: org\n  email: a@b.co\n  founded: 2024\n"
        "  name: Org\n  slug: org\n",
        encoding="utf-8",
    )
    (spec_dir / "architecture.yaml").write_text(
        "environments:\n  - name: dev\ndomains:\n  - name: d1\n    description: x\n"
        "    data_domains: {controls: [], creates: [], consumes: []}\n    repos: []\n",
        encoding="utf-8",
    )
    (spec_dir / "catalog.yaml").write_text(
        "data_dictionaries: []\n", encoding="utf-8"
    )


def test_no_stub_is_bootstrap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = discover(tmp_path)
    assert not r.ok
    assert r.error is None


def test_stub_points_to_valid_umbrella(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lp = tmp_path
    umb = lp / "myslug"
    _write_minimal_specs(umb / "Specifications")
    write_stub(lp, "myslug")
    r = discover(lp)
    assert r.ok
    assert r.slug == "myslug"


def test_stub_slug_mismatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lp = tmp_path
    umb = lp / "wrong"
    _write_minimal_specs(umb / "Specifications")
    write_stub(lp, "wrong")
    r = discover(lp)
    assert not r.ok
    assert "must match" in (r.error or "")


def test_stub_missing_specs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lp = tmp_path
    (lp / "myslug").mkdir()
    write_stub(lp, "myslug")
    r = discover(lp)
    assert not r.ok
    assert "Specifications" in (r.error or "")


def test_invalid_stub_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stub_path(tmp_path).write_text("bareword\n", encoding="utf-8")
    r = discover(tmp_path)
    assert not r.ok
    assert "Invalid .stage0-launch.yaml" in (r.error or "")


def test_two_umbrellas_without_stub_still_bootstrap(tmp_path, monkeypatch):
    """Multiple sibling umbrellas do not matter until a stub names one."""
    monkeypatch.chdir(tmp_path)
    lp = tmp_path
    write_three_specs(lp / "slug_a" / "Specifications", slug="slug_a")
    write_three_specs(lp / "slug_b" / "Specifications", slug="slug_b")
    r = discover(lp)
    assert not r.ok
    assert r.error is None
