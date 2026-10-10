import os
from pathlib import Path

import pytest

import compass_core.languages.python  # noqa: F401
from compass_core.errors import InvalidArgumentError
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.phases.pipeline import Pipeline
from compass_core.query.impact import bare_call_name, impact
from compass_core.query.params import ImpactParams
from compass_core.query.results import (
    AmbiguousReference,
    ImpactResult,
    Lookup,
    SymbolNotFound,
)
from compass_core.query.types import (
    CallType,
    CaveatCode,
    EdgeType,
    MatchRule,
    SymbolKind,
    ViaKind,
)


def _ok(res: Lookup[ImpactResult]) -> ImpactResult:
    assert isinstance(res, ImpactResult), res
    return res


def _run(db: GraphDB, loc: IndexLocation, ref: str, **params: float) -> ImpactResult:
    return _ok(impact(db, loc, ref, ImpactParams(**params)))


def _items(res: ImpactResult) -> list[tuple[int, str, str]]:
    """(distance, file_path, symbol id) for every item, in result order."""
    return [(g.distance, g.file_path, i.symbol.id) for g in res.groups for i in g.items]


def _ingest(repo: Path) -> IndexLocation:
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    return require_index(repo)


# --- file targets -------------------------------------------------------------------------


def test_file_target_lists_importers_at_distance_one(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py", depth=1)
    assert res.target.kind is SymbolKind.FILE and res.target.id == "file::app/auth.py"
    assert res.matched_by is MatchRule.FILE_PATH
    assert {g.file_path for g in res.groups} == {
        "app/api.py",
        "app/cli.py",
        "app/jobs.py",
        "app/__init__.py",
    }
    assert all(g.distance == 1 for g in res.groups)
    assert res.total == 4 and not res.truncated and res.affected_file_count == 4


def test_file_target_items_are_files_reached_via_imports(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py", depth=1)
    for group in res.groups:
        (item,) = group.items
        assert item.symbol.kind is SymbolKind.FILE
        assert item.symbol.id == f"file::{group.file_path}"
        assert item.via is not None and item.via.kind is ViaKind.IMPORTS
        assert item.via.symbol.id == "file::app/auth.py"
        assert item.min_confidence is None


def test_file_target_walks_transitively_and_sorts(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py", depth=3)
    assert _items(res) == [
        (1, "app/__init__.py", "file::app/__init__.py"),
        (1, "app/api.py", "file::app/api.py"),
        (1, "app/cli.py", "file::app/cli.py"),
        (1, "app/jobs.py", "file::app/jobs.py"),
        (2, "app/scheduler.py", "file::app/scheduler.py"),
    ]
    scheduler = res.groups[-1].items[0]
    assert scheduler.via is not None and scheduler.via.symbol.id == "file::app/jobs.py"


def test_file_target_via_calls_when_no_import(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    # models.py is imported only by api.py; User.save -> Base.save is a same-file call, so
    # the only dependent is api.py through its import.
    res = _run(fixture_db, fixture_index, "app/models.py")
    assert _items(res) == [(1, "app/api.py", "file::app/api.py")]


def test_file_target_edges_cover_imports_and_calls(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py", depth=1)
    pairs = {(e.type, e.source_id, e.target_id) for e in res.edges}
    assert (EdgeType.IMPORTS, "file::app/api.py", "file::app/auth.py") in pairs
    assert (EdgeType.CALLS, "app/api.py::handle", "app/auth.py::decode_token") in pairs
    assert len(pairs) == len(res.edges)  # deduplicated


def test_target_without_dependents_is_empty_not_error(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/util.py")
    assert res.groups == () and res.total == 0 and not res.truncated
    assert res.affected_file_count == 0 and res.edges == ()


def test_truncation_flag(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py", limit=1)
    assert res.truncated and res.total == 5
    assert _items(res) == [(1, "app/__init__.py", "file::app/__init__.py")]


def test_file_target_unresolved_caveat_counts_affected_functions(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    # Affected files' functions with raw calls lacking an edge: handle (User().save) and
    # jobs.run (same-file nightly()).
    res = _run(fixture_db, fixture_index, "app/auth.py")
    (caveat,) = [c for c in res.caveats if c.code is CaveatCode.UNRESOLVED_CALLS]
    assert caveat.count == 2 and "2" in caveat.message


# --- symbol targets -----------------------------------------------------------------------


def test_symbol_target_lists_direct_callers(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py::decode_token", depth=1)
    assert res.matched_by is MatchRule.EXACT_ID
    assert _items(res) == [
        (1, "app/api.py", "app/api.py::handle"),
        (1, "app/cli.py", "app/cli.py::run"),
        (1, "app/jobs.py", "app/jobs.py::nightly"),
    ]
    for item in (i for g in res.groups for i in g.items):
        assert item.via is not None and item.via.kind is ViaKind.CALLS
        assert item.via.symbol.id == "app/auth.py::decode_token"
        assert item.min_confidence == 1.0
    assert res.affected_file_count == 3


def test_symbol_target_walks_reverse_calls_transitively(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py::decode_token", depth=3)
    assert (2, "app/scheduler.py", "app/scheduler.py::tick") in _items(res)
    tick = res.groups[-1].items[0]
    assert tick.distance == 2 and tick.via is not None
    assert tick.via.kind is ViaKind.CALLS and tick.via.symbol.id == "app/jobs.py::nightly"
    assert tick.min_confidence == 1.0
    assert res.total == 4 and res.affected_file_count == 4


def test_depth_limits_the_walk(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py::decode_token", depth=1)
    assert "app/scheduler.py::tick" not in {i for _, _, i in _items(res)}
    assert max(g.distance for g in res.groups) == 1


def test_symbol_edges_carry_call_metadata(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py::decode_token", depth=3)
    by_pair = {(e.source_id, e.target_id): e for e in res.edges}
    edge = by_pair[("app/scheduler.py::tick", "app/jobs.py::nightly")]
    assert edge.type is EdgeType.CALLS and edge.call_type is CallType.DIRECT_IMPORT
    assert edge.confidence == 1.0
    assert len(res.edges) == 4


def test_mro_edge_confidence_propagates(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _run(fixture_db, fixture_index, "app/models.py::Base.save")
    ((distance, _, sid),) = _items(res)
    item = res.groups[0].items[0]
    assert (distance, sid) == (1, "app/models.py::User.save")
    assert item.via is not None and item.via.kind is ViaKind.CALLS
    assert item.min_confidence == pytest.approx(0.8)
    (edge,) = res.edges
    assert edge.call_type is CallType.MRO


def test_min_confidence_excludes_weaker_edges(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/models.py::Base.save", min_confidence=0.9)
    assert res.groups == () and res.total == 0 and res.edges == ()


def test_unresolved_same_file_call_yields_caveat_not_certainty(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py::parse")
    assert res.groups == () and res.total == 0
    (caveat,) = [c for c in res.caveats if c.code is CaveatCode.UNRESOLVED_CALLS]
    assert caveat.count is not None and caveat.count >= 1
    assert str(caveat.count) in caveat.message


def test_caveat_counts_callers_without_edge_to_target(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    # tick's only call resolves, so (b) adds nothing; jobs.run calls nightly() in the same
    # file without an edge, so (a) counts exactly one function.
    res = _run(fixture_db, fixture_index, "app/jobs.py::nightly", depth=1)
    assert _items(res) == [(1, "app/scheduler.py", "app/scheduler.py::tick")]
    (caveat,) = [c for c in res.caveats if c.code is CaveatCode.UNRESOLVED_CALLS]
    assert caveat.count == 1


def test_class_target_includes_subclasses_and_method_callers(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/models.py::Base", depth=2)
    items = {i.symbol.id: i for g in res.groups for i in g.items}
    assert set(items) == {
        "app/models.py::User",
        "app/models.py::User.save",
        "app/models.py::Admin",
    }
    user, user_save, admin = (
        items["app/models.py::User"],
        items["app/models.py::User.save"],
        items["app/models.py::Admin"],
    )
    assert user.distance == 1 and user.via is not None
    assert user.via.kind is ViaKind.INHERITS and user.via.symbol.id == "app/models.py::Base"
    assert user.min_confidence is None
    assert user_save.distance == 1 and user_save.via is not None
    assert user_save.via.kind is ViaKind.CALLS
    assert user_save.via.symbol.id == "app/models.py::Base.save"
    assert admin.distance == 2 and admin.via is not None
    assert admin.via.kind is ViaKind.INHERITS and admin.via.symbol.id == "app/models.py::User"
    assert [i.symbol.name for i in res.groups[0].items] == ["User", "save"]
    assert res.affected_file_count == 1


def test_class_target_depth_one_excludes_grandchildren(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _run(fixture_db, fixture_index, "app/models.py::Base", depth=1)
    assert "app/models.py::Admin" not in {i for _, _, i in _items(res)}
    inherits = [e for e in res.edges if e.type is EdgeType.INHERITS]
    assert [(e.source_id, e.target_id) for e in inherits] == [
        ("app/models.py::User", "app/models.py::Base")
    ]
    assert inherits[0].confidence is None and inherits[0].call_type is None


# --- references and params ----------------------------------------------------------------


def test_ambiguous_ref_returns_candidates(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = impact(fixture_db, fixture_index, "run", ImpactParams())
    assert isinstance(res, AmbiguousReference)
    assert {c.id for c in res.candidates} == {"app/cli.py::run", "app/jobs.py::run"}


@pytest.mark.parametrize("ref", ["no_such_symbol", "", "   "])
def test_unknown_or_blank_ref_is_not_found(
    fixture_db: GraphDB, fixture_index: IndexLocation, ref: str
) -> None:
    assert isinstance(impact(fixture_db, fixture_index, ref, ImpactParams()), SymbolNotFound)


def test_depth_bounds_are_enforced_by_params() -> None:
    with pytest.raises(InvalidArgumentError):
        ImpactParams(depth=0)
    with pytest.raises(InvalidArgumentError):
        ImpactParams(depth=11)


def test_result_header_and_depth(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _run(fixture_db, fixture_index, "app/auth.py::decode_token", depth=2)
    assert res.depth == 2
    assert res.index.repo_root == fixture_index.repo_root.resolve()
    assert not any(c.code is CaveatCode.STALE_INDEX for c in res.caveats)


# --- private repos ------------------------------------------------------------------------


def test_cycle_terminates_and_lists_each_node_once(tmp_path: Path) -> None:
    repo = tmp_path / "cycle"
    repo.mkdir()
    (repo / "a.py").write_text("from b import b\n\n\ndef a():\n    return b()\n")
    (repo / "b.py").write_text("from a import a\n\n\ndef b():\n    return a()\n")
    location = _ingest(repo)

    with GraphDB(location.db_path, read_only=True) as db:
        res = _ok(impact(db, location, "a.py::a", ImpactParams(depth=5)))

    assert _items(res) == [(1, "b.py", "b.py::b")]  # b once; the target never lists itself
    assert res.total == 1


def test_stale_index_adds_caveat(tmp_path: Path) -> None:
    repo = tmp_path / "stale"
    repo.mkdir()
    (repo / "m.py").write_text("def f():\n    return 1\n")
    location = _ingest(repo)
    future = (repo / "m.py").stat().st_mtime + 120
    os.utime(repo / "m.py", (future, future))

    with GraphDB(location.db_path, read_only=True) as db:
        res = _ok(impact(db, location, "m.py::f", ImpactParams()))

    (caveat,) = [c for c in res.caveats if c.code is CaveatCode.STALE_INDEX]
    assert caveat.count == 1 and res.index.stale_file_count == 1


@pytest.mark.parametrize(
    ("raw", "name"),
    [
        ("parse", "parse"),
        ("User().save", "save"),
        ("super().save", "save"),
        ("getattr(obj, name)", "getattr"),
        ("json.dumps", "dumps"),
        ("f(g(x)).h", "h"),
    ],
)
def test_bare_call_name(raw: str, name: str) -> None:
    assert bare_call_name(raw) == name
