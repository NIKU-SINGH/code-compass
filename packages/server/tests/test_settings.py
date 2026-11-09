"""Tests for compass_server.settings."""

from compass_server.settings import ServerSettings


def test_defaults():
    cfg = ServerSettings()
    assert cfg.API_HOST == "127.0.0.1"
    assert cfg.API_PORT == 8000
    assert cfg.FRONTEND_URL == "http://localhost:3000"


def test_env_override(monkeypatch):
    monkeypatch.setenv("API_PORT", "9123")
    monkeypatch.setenv("FRONTEND_PORT", "4000")
    cfg = ServerSettings()
    assert cfg.API_PORT == 9123
    assert cfg.FRONTEND_URL == "http://localhost:4000"


def test_inherits_engine_settings(monkeypatch):
    monkeypatch.setenv("QUERY_TIMEOUT_MS", "1234")
    assert ServerSettings().QUERY_TIMEOUT_MS == 1234
