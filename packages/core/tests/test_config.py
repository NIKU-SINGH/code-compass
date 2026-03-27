"""Tests for compass_core.config."""

import os
from pathlib import Path
from unittest.mock import patch

from compass_core.config import KUZU_DB_PATH, LLM_MODEL, REPO_ROOT


def test_default_kuzu_db_path():
    assert KUZU_DB_PATH == os.getenv("KUZU_DB_PATH", ".compass/graph.kuzu")


def test_default_llm_model():
    assert LLM_MODEL == os.getenv("LLM_MODEL", "gpt-4o-mini")


def test_repo_root_is_path():
    assert isinstance(REPO_ROOT, Path)


def test_env_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
    # Re-import to pick up the new env var
    import importlib

    import compass_core.config as cfg

    importlib.reload(cfg)
    assert cfg.LLM_MODEL == "claude-3-5-sonnet-20241022"
