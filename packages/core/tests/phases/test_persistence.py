from pathlib import Path

from compass_core.graph.db import GraphDB
from compass_core.graph.schema import create_schema
from compass_core.ir.graph import ResolvedGraph
from compass_core.ir.models import Definition, ParsedFile
from compass_core.phases.base import IngestContext
from compass_core.phases.persistence import PersistencePhase
from compass_core.shared_types import SymbolKind


def _pf_with_function(path: str, module: str) -> ParsedFile:
    fn = Definition(
        id=f"py::{module}::run",
        kind=SymbolKind.FUNCTION,
        name="run",
        file_path=path,
        line_start=1,
        line_end=2,
        source="def run(): pass",
        docstring=None,
        bases=[],
        parent_id=None,
        signature="def run()",
        decorators=[],
        raw_calls=[],
    )
    return ParsedFile(
        path=path,
        language="python",
        module_name=module,
        content_hash="x",
        definitions=[fn],
        imports=[],
        call_sites=[],
    )


def test_persists_files_and_functions(tmp_path: Path):
    db_path = tmp_path / "graph.ladybug"
    graph = ResolvedGraph(files=[_pf_with_function("a.py", "a")])
    ctx = IngestContext(repo_root=tmp_path)
    ctx.resolved_graph = graph

    with GraphDB(db_path) as db:
        create_schema(db)
        result = PersistencePhase().run(ctx, db)
        assert result.resolved_graph is not None
        assert result.write_result is not None
        assert result.write_result.node_count >= 1
        count = db.execute("MATCH (f:Function) RETURN count(f) AS c").get_next()[0]
        assert count == 1
