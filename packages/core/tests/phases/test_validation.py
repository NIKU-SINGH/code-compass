from pathlib import Path

from compass_core.ir.graph import CallEdge, ImportEdge, ResolvedGraph
from compass_core.ir.models import ParsedFile
from compass_core.phases.base import IngestContext
from compass_core.phases.validation import ValidationPhase


def _pf(path: str, degraded: bool = False) -> ParsedFile:
    return ParsedFile(
        path=path,
        language="python",
        module_name=path,
        content_hash="x",
        definitions=[],
        imports=[],
        call_sites=[],
        degraded=degraded,
    )


def test_report_counts_degraded_files(tmp_path: Path):
    graph = ResolvedGraph(files=[_pf("a.py"), _pf("b.py", degraded=True)])
    ctx = IngestContext(repo_root=tmp_path)
    ctx.resolved_graph = graph

    result = ValidationPhase().run(ctx)

    assert result.report is not None
    assert result.report.degraded_file_count == 1


def test_report_counts_dangling_imports(tmp_path: Path):
    graph = ResolvedGraph(
        files=[_pf("a.py")],
        import_edges=[ImportEdge(from_path="a.py", to_path="does_not_exist.py")],
    )
    ctx = IngestContext(repo_root=tmp_path)
    ctx.resolved_graph = graph

    result = ValidationPhase().run(ctx)

    assert result.report.dangling_import_count == 1


def test_report_computes_resolved_percentage_per_language(tmp_path: Path):
    graph = ResolvedGraph(
        files=[_pf("a.py")],
        call_edges=[
            CallEdge(
                caller_id="py::a::f", callee_id="py::a::g", call_type="RESOLVED", confidence=1.0
            )
        ],
    )
    ctx = IngestContext(repo_root=tmp_path)
    ctx.resolved_graph = graph

    result = ValidationPhase().run(ctx)

    assert result.report.resolved_by_language["python"] == 1.0
