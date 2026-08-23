from pathlib import Path

import compass_core.languages.python  # noqa: F401
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
