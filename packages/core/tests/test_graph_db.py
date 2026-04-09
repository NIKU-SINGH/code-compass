from pathlib import Path

from compass_core.graph.db import GraphDB


def test_initialization(tmp_path: Path) -> None:
    db = GraphDB(tmp_path / "test.ladybug")
    assert db is not None
    db.close()
