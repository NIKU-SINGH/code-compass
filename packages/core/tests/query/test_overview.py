import os
from pathlib import Path

import compass_core.languages.python  # noqa: F401
from compass_core.contract.results import OverviewResult
from compass_core.contract.types import CaveatCode
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.phases.pipeline import Pipeline
from compass_core.query.overview import overview
from compass_core.shared_types import EdgeType, SymbolKind


def _build(tmp_path: Path, files: dict[str, str]) -> IndexLocation:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    return require_index(repo)


def _overview(location: IndexLocation) -> OverviewResult:
    with GraphDB(location.db_path, read_only=True) as db:
        return overview(db, location)


def test_counts(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    counts = overview(fixture_db, fixture_index).counts
    assert counts.files == 8 and counts.classes == 3
    assert counts.functions == 11
    assert set(counts.edges_by_type) == set(EdgeType)
    assert counts.edges_by_type[EdgeType.IMPORTS] == 6
    assert counts.edges_by_type[EdgeType.CALLS] == 5
    assert counts.edges_by_type[EdgeType.CALLS_EXTERN] >= 1


def test_most_imported_file_is_auth(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    top = overview(fixture_db, fixture_index).most_imported_files
    assert top[0].symbol.file_path == "app/auth.py"
    assert top[0].symbol.kind is SymbolKind.FILE
    assert top[0].count == 4
    assert [r.count for r in top] == sorted((r.count for r in top), reverse=True)


def test_most_called_function_is_decode_token(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    top = overview(fixture_db, fixture_index).most_called_functions
    assert top[0].symbol.name == "decode_token" and top[0].count == 3


def test_riskiest_is_decode_token(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    top = overview(fixture_db, fixture_index).riskiest_to_change
    assert top[0].symbol.name == "decode_token"
    assert top[0].count == 4


def test_external_libraries(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    libs = {
        lib.library: lib.call_count
        for lib in overview(fixture_db, fixture_index).top_external_libraries
    }
    assert libs.get("json") == 1


def test_entry_points_are_files_nobody_imports(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    entries = overview(fixture_db, fixture_index).entry_points
    paths = [e.file_path for e in entries]
    assert paths == sorted(paths) and len(paths) <= 5
    assert all(e.kind is SymbolKind.FILE for e in entries)
    assert "app/auth.py" not in paths and "app/scheduler.py" in paths


def test_fresh_fixture_has_no_caveats(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    assert overview(fixture_db, fixture_index).caveats == ()


def _module(name: str, callee: str | None) -> str:
    if callee is None:
        return f"def {name}():\n    pass\n"
    return f"from {callee} import {callee}\n\ndef {name}():\n    return {callee}()\n"


# Calls resolve across modules: leaf <- a <- b <- c <- d, and hub <- x, y.
_CHAIN = {
    "leaf.py": _module("leaf", None),
    "a.py": _module("a", "leaf"),
    "b.py": _module("b", "a"),
    "c.py": _module("c", "b"),
    "d.py": _module("d", "c"),
    "hub.py": _module("hub", None),
    "x.py": _module("x", "hub"),
    "y.py": _module("y", "hub"),
}


def test_riskiest_ranks_by_affected_not_fan_in(tmp_path: Path) -> None:
    res = _overview(_build(tmp_path, _CHAIN))
    ranked = [(r.symbol.name, r.count) for r in res.riskiest_to_change]
    # leaf affects a, b, c (d is beyond depth 3) and a affects b, c, d, both with fan-in 1;
    # hub has the larger fan-in (2) but affects only x and y. Equal counts tie by name.
    assert ranked == [("a", 3), ("leaf", 3), ("b", 2), ("hub", 2), ("c", 1)]
    counts = [c for _, c in ranked]
    assert counts == sorted(counts, reverse=True) and len(ranked) <= 5
    called = {r.symbol.name: r.count for r in res.most_called_functions}
    assert called["hub"] == 2 and called["leaf"] == 1


def test_stale_index_adds_caveat(tmp_path: Path) -> None:
    location = _build(tmp_path, _CHAIN)
    future = 4_000_000_000
    os.utime(location.repo_root / "leaf.py", (future, future))
    res = _overview(location)
    assert [c.code for c in res.caveats] == [CaveatCode.STALE_INDEX]
    assert res.caveats[0].count == 1


def test_no_resolved_calls_adds_unresolved_caveat(tmp_path: Path) -> None:
    res = _overview(_build(tmp_path, {"m.py": "def f():\n    pass\n\ndef g():\n    f()\n"}))
    assert res.counts.edges_by_type[EdgeType.CALLS] == 0
    [caveat] = res.caveats
    assert caveat.code is CaveatCode.UNRESOLVED_CALLS and caveat.count == 2
    assert "no function-to-function calls were resolved" in caveat.message


def test_empty_index_has_empty_lists(tmp_path: Path) -> None:
    res = _overview(_build(tmp_path, {"x.py": "x = 1\n"}))
    assert res.counts.files == 1
    assert res.counts.functions == 0 and res.counts.classes == 0
    assert set(res.counts.edges_by_type) == set(EdgeType)
    assert res.counts.edges_by_type[EdgeType.CALLS] == 0
    assert res.most_called_functions == () and res.most_imported_files == ()
    assert res.top_external_libraries == () and res.riskiest_to_change == ()
    assert res.caveats == ()
    assert [e.file_path for e in res.entry_points] == ["x.py"]


def test_call_resolution_counts_every_call_site(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    calls = overview(fixture_db, fixture_index).call_resolution
    assert calls.total > calls.resolved >= 5


def test_call_resolution_of_unlinked_call_is_unresolved(tmp_path: Path) -> None:
    res = _overview(_build(tmp_path, {"m.py": "def f():\n    pass\n\ndef g():\n    f()\n"}))
    assert (res.call_resolution.total, res.call_resolution.resolved) == (1, 0)


def test_call_resolution_of_empty_index_is_zero(tmp_path: Path) -> None:
    res = _overview(_build(tmp_path, {"x.py": "x = 1\n"}))
    assert (res.call_resolution.total, res.call_resolution.resolved) == (0, 0)
