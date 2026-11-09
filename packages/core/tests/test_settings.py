"""Tests for compass_core.settings."""

from pathlib import Path

from compass_core.settings import Settings, settings


def test_default_ladybug_db_path():
    assert settings.LADYBUG_DB_PATH == ".compass/graph.ladybug"


def test_repo_root_is_path():
    assert isinstance(settings.REPO_ROOT, Path)


def test_env_override(monkeypatch):
    monkeypatch.setenv("QUERY_TIMEOUT_MS", "9123")
    assert Settings().QUERY_TIMEOUT_MS == 9123
