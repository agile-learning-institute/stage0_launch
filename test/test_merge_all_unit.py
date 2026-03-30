import io
from pathlib import Path

import pytest

from stage0_launch.operations.merge_all import run_merge_all
from test.specs_minimal import write_three_specs


def test_merge_all_skip_umbrella_requires_specs(tmp_path):
    templates_root = tmp_path / "tmpl"
    (templates_root / "stage0_template_flask_mongo").mkdir(parents=True)
    specs = tmp_path / "specs"
    write_three_specs(specs, slug="u1")
    lp = tmp_path / "lp"
    log = io.StringIO()
    with pytest.raises(RuntimeError, match="--skip-umbrella requires"):
        run_merge_all(
            lp,
            specs,
            templates_root,
            log,
            skip_umbrella=True,
        )


def test_merge_all_materializes_and_merges(monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_merge(_log, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "stage0_launch.operations.merge_all.run_runbook_merge",
        fake_merge,
    )

    specs = tmp_path / "specs"
    write_three_specs(specs, slug="u1")
    root = tmp_path / "templates"
    (root / "stage0_template_umbrella").mkdir(parents=True)
    (root / "stage0_template_umbrella" / "u.txt").write_text("u", encoding="utf-8")
    (root / "stage0_template_flask_mongo").mkdir(parents=True)
    (root / "stage0_template_flask_mongo" / "f.txt").write_text("f", encoding="utf-8")

    lp = tmp_path / "lp"
    log = io.StringIO()
    run_merge_all(lp, specs, root, log, emit_launchpad_stub=True)

    assert (lp / "u1" / "u.txt").read_text() == "u"
    assert (lp / "u1_svc1" / "f.txt").read_text() == "f"
    assert (lp / "u1" / "Specifications" / "product.yaml").is_file()

    assert len(calls) == 2
    assert calls[0]["service_name"] is None
    assert calls[0]["specifications_dir"] == specs.resolve()
    assert calls[1]["service_name"] == "dom1"
    assert calls[1]["specifications_dir"] == (lp / "u1" / "Specifications").resolve()

    assert (lp / ".stage0-launch.yaml").is_file()
