from pathlib import Path

import pytest

from compass_core.errors import IndexNotFoundError
from compass_core.index.locate import find_index, locate_index, require_index
from compass_core.settings import settings


def _make_index(root: Path) -> Path:
    db = root / ".compass" / "graph.ladybug"
    db.parent.mkdir(parents=True)
    db.write_text("")
    return db


def test_found_in_cwd(tmp_path: Path):
    db = _make_index(tmp_path)
    loc = find_index(tmp_path)
    assert loc is not None and loc.db_path == db and loc.repo_root == tmp_path


def test_found_in_parent(tmp_path: Path):
    _make_index(tmp_path)
    child = tmp_path / "pkg" / "sub"
    child.mkdir(parents=True)
    loc = find_index(child)
    assert loc is not None and loc.repo_root == tmp_path


def test_not_found_returns_none(tmp_path: Path):
    assert find_index(tmp_path) is None


def test_require_index_raises_when_missing(tmp_path: Path):
    with pytest.raises(IndexNotFoundError) as exc:
        require_index(tmp_path)
    assert exc.value.searched_from == tmp_path


def test_override_takes_precedence(tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    db = _make_index(other)
    loc = require_index(tmp_path, override=db)
    assert loc.db_path == db


def test_locate_index_prefers_existing_configured_path(tmp_path: Path, monkeypatch):
    configured = _make_index(tmp_path / "configured")
    elsewhere = tmp_path / "elsewhere"
    _make_index(elsewhere)
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(configured))
    loc = locate_index(elsewhere)
    assert loc.db_path == configured.resolve()
    assert loc.repo_root == (tmp_path / "configured").resolve()


def test_locate_index_walks_up_when_configured_path_is_missing(tmp_path: Path, monkeypatch):
    _make_index(tmp_path)
    child = tmp_path / "pkg"
    child.mkdir()
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(tmp_path / "missing.ladybug"))
    assert locate_index(child).repo_root == tmp_path


def test_locate_index_raises_when_nothing_is_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(tmp_path / "missing.ladybug"))
    with pytest.raises(IndexNotFoundError):
        locate_index(tmp_path)
