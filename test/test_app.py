import json

import pytest

from stage0_launch.app import create_app
from stage0_launch.launchpad_stub import write_stub
from test.specs_minimal import MIN_ARCH, MIN_CATALOG, MIN_PRODUCT, write_three_specs


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_index_ok(client):
    r = client.get("/")
    assert r.status_code == 200


def test_thanks_page_ok(client):
    r = client.get("/thanks")
    assert r.status_code == 200
    assert b"Thanks for launching" in r.data
    assert b"btn-exit" in r.data


def test_exit_page_ok(client):
    r = client.get("/exit")
    assert r.status_code == 200
    assert b"stopping" in r.data.lower()


def test_api_shutdown_ok(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "stage0_launch.app.CONTAINER_LAUNCHPAD",
        tmp_path / "__no_shutdown__",
    )
    r = client.post("/api/shutdown")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_bootstrap_finish_400_without_stub(client, tmp_path):
    r = client.post("/api/bootstrap/finish")
    assert r.status_code == 400
    assert "stub" in (r.get_json() or {}).get("error", "").lower()


def test_bootstrap_finish_removes_bootstrap_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "stage0_launch.app.CONTAINER_LAUNCHPAD",
        tmp_path / "__not_container_mount__",
    )
    write_three_specs(tmp_path / "p9" / "Specifications", slug="p9")
    write_stub(tmp_path, "p9")
    boot = tmp_path / ".stage0-bootstrap"
    (boot / "specs").mkdir(parents=True)
    (boot / "specs" / "product.yaml").write_text("x", encoding="utf-8")

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.post("/api/bootstrap/finish")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert not boot.exists()


def test_api_status_bootstrap_no_stub(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["bootstrap_mode"] is True
    assert data["interactive_mode"] is False
    assert "launchpad_dir_warning" in data


def test_api_status_interactive_with_stub(client, tmp_path):
    write_three_specs(tmp_path / "p9" / "Specifications", slug="p9")
    write_stub(tmp_path, "p9")
    r = client.get("/api/status")
    data = r.get_json()
    assert data["bootstrap_mode"] is False
    assert data["interactive_mode"] is True
    assert data["slug"] == "p9"
    assert "dom1" in (data.get("services") or [])


def test_api_status_invalid_stub(client, tmp_path):
    (tmp_path / ".stage0-launch.yaml").write_text("foo: bar\n", encoding="utf-8")
    r = client.get("/api/status")
    data = r.get_json()
    assert data["bootstrap_mode"] is False
    assert data["interactive_mode"] is False
    assert data["discovery_error"]


def test_api_specs_validate_ok(client):
    body = {
        "product_yaml": MIN_PRODUCT.format(slug="p1"),
        "architecture_yaml": MIN_ARCH,
        "catalog_yaml": MIN_CATALOG,
    }
    r = client.post(
        "/api/specs/validate",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["errors"] == []


def test_api_specs_validate_bad_yaml(client):
    body = {
        "product_yaml": MIN_PRODUCT.format(slug="p1"),
        "architecture_yaml": "domains: [\n",
        "catalog_yaml": MIN_CATALOG,
    }
    r = client.post(
        "/api/specs/validate",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is False
    assert any("invalid YAML" in e for e in data["errors"])


def test_launchpad_warning_when_nonempty_bootstrap(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    (tmp_path / "other_repo").mkdir()
    (tmp_path / "stage0_launch").mkdir()
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.get("/api/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["bootstrap_mode"] is True
    w = data["launchpad_dir_warning"]
    assert w is not None
    assert w["path"] == str(tmp_path)
    assert set(w["items"]) == {"other_repo", "stage0_launch"}


def test_launchpad_warning_absent_when_empty_bootstrap(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.get("/api/status")
    data = r.get_json()
    assert data["bootstrap_mode"] is True
    assert data["launchpad_dir_warning"] is None


def test_bootstrap_job_requires_pasted_specs(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.post("/api/jobs/bootstrap")
    assert r.status_code == 400
    assert "Paste" in (r.get_json() or {}).get("error", "")
