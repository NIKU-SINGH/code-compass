"""Tests for compass_core.settings."""

from pathlib import Path

from compass_core.settings import settings


def test_default_ladybug_db_path():
    assert settings.LADYBUG_DB_PATH == ".compass/graph.ladybug"


def test_repo_root_is_path():
    assert isinstance(settings.REPO_ROOT, Path)


def test_env_override(monkeypatch):
    monkeypatch.setenv("API_PORT", "9123")
    # Re-import to pick up the new env var
    import importlib

    import compass_core.settings as cfg

    importlib.reload(cfg)
    assert cfg.settings.API_PORT == 9123
