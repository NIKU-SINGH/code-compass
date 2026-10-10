import os
import shutil
from datetime import UTC
from pathlib import Path

import pytest

import compass_core.languages.python  # noqa: F401
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.phases.pipeline import Pipeline
from compass_core.query.status import index_status

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
def private_index(tmp_path: Path) -> IndexLocation:
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE, repo)
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    return require_index(repo)


def _status(loc: IndexLocation) -> int:
    with GraphDB(loc.db_path, read_only=True) as db:
        return index_status(loc, db).stale_file_count


def test_fresh_index_is_not_stale(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    status = index_status(fixture_index, fixture_db)
    assert status.stale_file_count == 0
    assert status.new_file_count is None
    assert status.repo_root.is_absolute()
    assert status.indexed_at.tzinfo is not None and status.indexed_at.tzinfo.utcoffset(None) == (
        UTC.utcoffset(None)
    )


def test_modified_file_is_stale(private_index: IndexLocation) -> None:
    target = private_index.repo_root / "app" / "auth.py"
    future = target.stat().st_mtime + 3600
    os.utime(target, (future, future))
    assert _status(private_index) == 1


def test_deleted_file_is_stale(private_index: IndexLocation) -> None:
    (private_index.repo_root / "app" / "util.py").unlink()
    assert _status(private_index) == 1


def test_whole_second_boundary(private_index: IndexLocation) -> None:
    target = private_index.repo_root / "app" / "auth.py"
    with GraphDB(private_index.db_path, read_only=True) as db:
        indexed_at = int(index_status(private_index, db).indexed_at.timestamp())
    os.utime(target, (indexed_at, indexed_at))
    assert _status(private_index) == 0
    os.utime(target, (indexed_at + 0.9, indexed_at + 0.9))
    assert _status(private_index) == 0  # same second as ingest: invisible by design
    os.utime(target, (indexed_at + 1, indexed_at + 1))
    assert _status(private_index) == 1
