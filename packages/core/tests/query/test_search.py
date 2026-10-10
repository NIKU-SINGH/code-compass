import pytest

from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.params import SearchParams
from compass_core.query.results import SearchResult
from compass_core.query.search import find_symbols
from compass_core.query.types import SearchMatch, SymbolKind


def _find(db: GraphDB, loc: IndexLocation, query: str, **kw: object) -> SearchResult:
    return find_symbols(db, loc, SearchParams(query=query, **kw))  # type: ignore[arg-type]


def test_exact_name_ranks_first(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "parse")
    assert res.hits[0].symbol.name == "parse" and res.hits[0].match is SearchMatch.EXACT


def test_match_class_outranks_higher_fan_in(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    # "h": handle/helper are PREFIX hits with fan_in 0; auth.py is only a SUBSTRING hit
    # but has fan_in 4. The better match class must still come first.
    res = _find(fixture_db, fixture_index, "h")
    summary = [(h.match, h.fan_in) for h in res.hits]
    assert summary[:2] == [(SearchMatch.PREFIX, 0)] * 2
    assert (SearchMatch.SUBSTRING, 4) in summary[2:]
    assert [h.symbol.name for h in res.hits[:2]] == ["handle", "helper"]


def test_fan_in_then_name_within_match_class(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _find(fixture_db, fixture_index, "t", limit=100)
    rank = list(SearchMatch).index
    keys = [(rank(h.match), -h.fan_in, h.symbol.name, h.symbol.id) for h in res.hits]
    assert keys == sorted(keys)
    assert [h.fan_in for h in res.hits[:2]] == [4, 3]


def test_exact_methods_ordered_by_fan_in(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "save")
    assert [(h.symbol.id, h.match, h.fan_in) for h in res.hits] == [
        ("app/models.py::Base.save", SearchMatch.EXACT, 1),
        ("app/models.py::User.save", SearchMatch.EXACT, 0),
    ]


def test_qualified_name_query(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "auth.decode_token")
    assert res.hits[0].symbol.id == "app/auth.py::decode_token"
    assert res.hits[0].match is SearchMatch.QUALIFIED_SUFFIX


def test_qualified_suffix_for_method(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "User.save")
    assert res.hits[0].symbol.id == "app/models.py::User.save"
    assert res.hits[0].match is SearchMatch.QUALIFIED_SUFFIX
    assert res.hits[0].symbol.kind is SymbolKind.METHOD


def test_same_bare_name_in_two_files(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "run", kind=SymbolKind.FUNCTION)
    assert sorted(h.symbol.file_path or "" for h in res.hits) == ["app/cli.py", "app/jobs.py"]
    assert all(h.match is SearchMatch.EXACT for h in res.hits)


def test_case_insensitive(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "USER", kind=SymbolKind.CLASS)
    assert res.hits[0].symbol.name == "User" and res.hits[0].match is SearchMatch.EXACT


def test_kind_filter(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "a", kind=SymbolKind.CLASS)
    assert {h.symbol.kind for h in res.hits} == {SymbolKind.CLASS}
    assert res.kind is SymbolKind.CLASS


def test_kind_filter_applies_before_limit(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _find(fixture_db, fixture_index, "a", kind=SymbolKind.CLASS, limit=1)
    all_classes = _find(fixture_db, fixture_index, "a", kind=SymbolKind.CLASS)
    assert len(res.hits) == 1 and res.total == len(all_classes.hits) > 1 and res.truncated


def test_method_and_function_kinds(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    methods = _find(fixture_db, fixture_index, "save", kind=SymbolKind.METHOD)
    assert {h.symbol.id for h in methods.hits} == {
        "app/models.py::Base.save",
        "app/models.py::User.save",
    }
    assert _find(fixture_db, fixture_index, "save", kind=SymbolKind.FUNCTION).hits == ()


def test_limit_and_total(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "a", limit=1)
    assert len(res.hits) == 1 and res.total > 1 and res.truncated


def test_not_truncated_when_all_fit(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "parse")
    assert res.total == len(res.hits) and not res.truncated


def test_files_are_searchable(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "auth.py")
    file_hits = [h for h in res.hits if h.symbol.kind is SymbolKind.FILE]
    assert [h.symbol.id for h in file_hits] == ["file::app/auth.py"]
    assert file_hits[0].fan_in == 4


def test_file_path_match_uses_relative_path(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    # The absolute repo root (a pytest tmp dir) must never match.
    res = _find(fixture_db, fixture_index, "sample_repo")
    assert res.hits == () and res.total == 0


@pytest.mark.parametrize("query", ["%", "'", '"', "\\", "a'; MATCH (n) DETACH DELETE n; //"])
def test_special_characters_are_literal(
    fixture_db: GraphDB, fixture_index: IndexLocation, query: str
) -> None:
    res = _find(fixture_db, fixture_index, query)
    assert res.hits == () and res.total == 0


def test_underscore_is_not_a_wildcard(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "decode_token")
    assert res.hits[0].match is SearchMatch.EXACT
    assert _find(fixture_db, fixture_index, "decode-token").hits == ()


def test_header(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    res = _find(fixture_db, fixture_index, "parse")
    assert res.query == "parse" and res.caveats == ()
    assert res.index.repo_root == fixture_index.repo_root.resolve()
    assert res.hits[0].symbol.id == "app/auth.py::parse"


def test_underscore_query_is_literal_text(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    res = _find(fixture_db, fixture_index, "_", limit=100)
    assert res.hits and all(
        "_" in h.symbol.name or "_" in (h.symbol.file_path or "") for h in res.hits
    )
