from pathlib import Path

import pytest

import compass_core.languages.python  # noqa: F401
from compass_core.graph.db import GraphDB, as_row
from compass_core.phases.pipeline import Pipeline


def test_full_pipeline_runs_end_to_end(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    helper()\n")
    (repo / "b.py").write_text("def helper():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"

    ctx = Pipeline().run(repo, db_path)

    assert ctx.manifest is not None and len(ctx.manifest.files) == 2
    assert ctx.parsed_files is not None and len(ctx.parsed_files) == 2
    assert ctx.resolved_graph is not None
    assert ctx.report is not None
    assert ctx.report.degraded_file_count == 0


def test_stop_after_resolution_skips_persistence(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n")
    db_path = tmp_path / "graph.ladybug"

    ctx = Pipeline().run(repo, db_path, stop_after="resolution")

    assert ctx.resolved_graph is not None
    assert not db_path.exists()


def _edge_count(db_path: Path) -> int:
    with GraphDB(db_path) as db:
        return int(as_row(db.execute("MATCH ()-[r]->() RETURN count(*)"))[0])


def _function_names(db_path: Path) -> set[str]:
    with GraphDB(db_path) as db:
        return {r[0] for r in db.execute("MATCH (f:Function) RETURN f.name").get_all()}


def test_reingest_does_not_duplicate_edges(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    helper()\n")
    (repo / "b.py").write_text("def helper():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"

    Pipeline().run(repo, db_path)
    first = _edge_count(db_path)
    Pipeline().run(repo, db_path)

    assert _edge_count(db_path) == first


def test_reingest_removes_deleted_functions(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def keep():\n    pass\n\ndef gone():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"
    Pipeline().run(repo, db_path)

    (repo / "a.py").write_text("def keep():\n    pass\n")
    Pipeline().run(repo, db_path)

    assert _function_names(db_path) == {"keep"}


def test_failed_ingest_leaves_old_db_untouched(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def keep():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"
    Pipeline().run(repo, db_path)
    before = _edge_count(db_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr("compass_core.phases.pipeline.PersistencePhase.run", boom)
    with pytest.raises(RuntimeError):
        Pipeline().run(repo, db_path)

    assert _edge_count(db_path) == before
    assert not db_path.with_name(db_path.name + ".building").exists()


def _calls_count(db_path: Path) -> int:
    with GraphDB(db_path) as db:
        return int(as_row(db.execute("MATCH ()-[r:CALLS]->() RETURN count(r)"))[0])


def test_write_result_counts_only_stored_edges(tmp_path: Path):
    """A resolved call to a class constructor has no Function callee, so the
    writer cannot store it: it must be reported as dropped, not as written."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "lib.py").write_text("class Widget:\n    pass\n\n\ndef helper():\n    pass\n")
    (repo / "app.py").write_text(
        "from lib import Widget, helper\n\n\n"
        "def build():\n    return Widget()\n\n\n"
        "def run():\n    helper()\n"
    )
    db_path = tmp_path / "graph.ladybug"

    ctx = Pipeline().run(repo, db_path)

    assert ctx.resolved_graph is not None
    assert len(ctx.resolved_graph.call_edges) == 2
    assert ctx.write_result is not None
    assert _calls_count(db_path) == 1
    assert ctx.write_result.dropped_edges == 1
    assert ctx.write_result.edge_count == _edge_count(db_path)


def test_custom_db_path_keeps_metadata_beside_the_db(tmp_path: Path):
    from compass_core.index.locate import require_index
    from compass_core.index.metadata import load_metadata
    from compass_core.query.status import index_status

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    pass\n")
    db_path = repo / "custom_index" / "g.ladybug"

    Pipeline().run(repo, db_path)

    assert not (repo / ".compass" / "metadata.json").exists()
    load_metadata(db_path.parent / "metadata.json")
    location = require_index(repo, override=db_path)
    with GraphDB(location.db_path, read_only=True) as db:
        status = index_status(location, db)
    assert status.repo_root == repo.resolve() and status.stale_file_count == 0
