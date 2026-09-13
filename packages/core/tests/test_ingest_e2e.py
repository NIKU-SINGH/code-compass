from pathlib import Path

import compass_core.languages.python  # noqa: F401
from compass_core.phases.pipeline import Pipeline


def test_ingest_pipeline_populates_db_for_small_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "models.py").write_text(
        "class Base:\n    pass\n\nclass User(Base):\n    def greet(self):\n        return hello()\n\n"
        "def hello():\n    return 'hi'\n"
    )
    db_path = tmp_path / ".compass" / "graph.ladybug"

    ctx = Pipeline().run(repo, db_path)

    assert ctx.report is not None
    assert ctx.report.degraded_file_count == 0
    assert db_path.exists()

    from compass_core.graph.db import GraphDB

    with GraphDB(db_path) as db:
        class_count = db.execute("MATCH (c:Class) RETURN count(c) AS c").get_next()[0]
        inherit_count = db.execute("MATCH ()-[r:INHERITS]->() RETURN count(r) AS c").get_next()[0]
        assert class_count == 2
        assert inherit_count == 1
