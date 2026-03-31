import json

import pytest

from stage0_launch.app import create_app
from stage0_launch.launchpad_stub import read_stub_umbrella, stub_path, write_stub
from test.specs_minimal import MIN_ARCH, MIN_CATALOG, MIN_PRODUCT, write_three_specs


def _client_with_launchpad(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


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
    assert b".stage0-bootstrap" in r.data
    assert b"CONTRIBUTING.md" in r.data
    assert b"btn-exit" in r.data


def test_thanks_shows_cli_from_product(monkeypatch, tmp_path):
    slug = "myslug"
    write_three_specs(tmp_path / slug / "Specifications", slug=slug)
    write_stub(tmp_path, slug)
    client = _client_with_launchpad(monkeypatch, tmp_path)
    r = client.get("/thanks")
    assert r.status_code == 200
    assert b"tp up all" in r.data
    assert b"myslug/CONTRIBUTING.md" in r.data


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
    err = (r.get_json() or {}).get("error", "").lower()
    assert "nothing to finish" in err or "no .stage0-bootstrap" in err


def test_bootstrap_finish_removes_bootstrap_only_after_failed_bootstrap(
    monkeypatch, tmp_path
):
    """Simulate failed job: specs dir exists, no stub yet — finish cleans up and exits ok."""
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "stage0_launch.app.CONTAINER_LAUNCHPAD",
        tmp_path / "__not_container_mount__",
    )
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
    assert not stub_path(tmp_path).is_file()


def test_bootstrap_finish_writes_stub_from_pasted_product_slug(monkeypatch, tmp_path):
    """After cleanup, ``.stage0-launch.yaml`` gets ``umbrella`` from pasted product.yaml."""
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "stage0_launch.app.CONTAINER_LAUNCHPAD",
        tmp_path / "__not_container_mount__",
    )
    write_three_specs(tmp_path / ".stage0-bootstrap" / "specs", slug="mentorhub")
    assert not stub_path(tmp_path).is_file()

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.post("/api/bootstrap/finish")
    assert r.status_code == 200
    assert not (tmp_path / ".stage0-bootstrap").exists()
    assert read_stub_umbrella(tmp_path) == "mentorhub"


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
    assert data.get("delete_enabled") is False


def test_api_status_delete_enabled_true(monkeypatch, client, tmp_path):
    monkeypatch.setenv("DELETE_ENABLED", "True")
    write_three_specs(tmp_path / "p9" / "Specifications", slug="p9")
    write_stub(tmp_path, "p9")
    r = client.get("/api/status")
    assert r.get_json().get("delete_enabled") is True


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


def test_api_delete_services_forbidden_when_delete_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    monkeypatch.delenv("DELETE_ENABLED", raising=False)
    write_three_specs(tmp_path / "p9" / "Specifications", slug="p9")
    write_stub(tmp_path, "p9")
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.post(
        "/api/jobs/delete-services",
        data=json.dumps(
            {
                "services": ["dom1"],
                "i_confirm_delete_services": "yes",
                "i_confirm_slug": "p9",
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 403
    assert "DELETE_ENABLED" in (r.get_json() or {}).get("error", "")


def test_api_delete_services_allowed_when_delete_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    monkeypatch.setenv("DELETE_ENABLED", "True")
    write_three_specs(tmp_path / "p9" / "Specifications", slug="p9")
    write_stub(tmp_path, "p9")
    monkeypatch.setattr("stage0_launch.app.cmd_delete_services", lambda *a, **k: None)
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.post(
        "/api/jobs/delete-services",
        data=json.dumps(
            {
                "services": ["dom1"],
                "i_confirm_delete_services": "yes",
                "i_confirm_slug": "p9",
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert "job_id" in r.get_json()


def test_api_build_services_starts_job(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUNCHPAD_DIR", str(tmp_path))
    write_three_specs(tmp_path / "p9" / "Specifications", slug="p9")
    write_stub(tmp_path, "p9")

    def fake_build(ctx, services, log):
        log.write(f"stub build {services}\n")

    monkeypatch.setattr("stage0_launch.app.cmd_build_services", fake_build)
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    r = c.post(
        "/api/jobs/build-services",
        data=json.dumps({"services": ["dom1"]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert "job_id" in r.get_json()
