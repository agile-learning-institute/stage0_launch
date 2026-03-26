from pathlib import Path

import pytest

from stage0_launch.operations.umbrella_ops import (
    npm_env_for_github_packages,
    npm_github_packages_auth_env,
)


def test_npm_env_empty_when_node_auth_set(monkeypatch):
    monkeypatch.setenv("NODE_AUTH_TOKEN", "already-set")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_not_override")
    assert npm_env_for_github_packages() == {}


def test_npm_env_from_github_token(monkeypatch):
    monkeypatch.delenv("NODE_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_github")
    assert npm_env_for_github_packages() == {"NODE_AUTH_TOKEN": "ghp_from_github"}


def test_npm_env_prefers_existing_node_auth(monkeypatch):
    monkeypatch.setenv("NODE_AUTH_TOKEN", "custom")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_other")
    assert npm_env_for_github_packages() == {}


def test_npm_env_gh_token_fallback(monkeypatch):
    monkeypatch.delenv("NODE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gh_token_only")
    assert npm_env_for_github_packages() == {"NODE_AUTH_TOKEN": "gh_token_only"}


def test_npm_env_empty_without_any_token(monkeypatch):
    for k in ("NODE_AUTH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert npm_env_for_github_packages() == {}


def test_npm_auth_env_yields_none_without_token(monkeypatch):
    for k in ("NODE_AUTH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with npm_github_packages_auth_env() as extra:
        assert extra is None


def test_npm_auth_env_sets_userconfig_and_node_auth(monkeypatch):
    monkeypatch.delenv("NODE_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    with npm_github_packages_auth_env() as extra:
        assert extra is not None
        assert extra["NODE_AUTH_TOKEN"] == "ghp_test_token"
        path = extra["NPM_CONFIG_USERCONFIG"]
        with open(path, encoding="utf-8") as f:
            assert "_authToken=ghp_test_token" in f.read()
    assert not Path(path).is_file()
