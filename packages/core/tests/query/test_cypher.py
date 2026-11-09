"""Every ``Query`` in the query layer runs against a real index and decodes its rows.

The queries are collected from the query modules, so a new query is covered without
being listed here. A typo in a label, property or relationship name, a parameter that
is never supplied, or a decoder that disagrees with its ``RETURN`` columns fails here
instead of on the code path that happens to use it.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from collections.abc import Iterator

import pytest

import compass_core.query as query_package
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.cypher import Query
from compass_core.query.references import DefinitionQueries

# One value per parameter name, chosen so most queries return rows from the fixture repo.
SAMPLE_PARAMS: dict[str, object] = {
    "ids": [
        "py::app.auth::decode_token",
        "py::app.models::Base",
        "py::app.models::User",
        "json.dumps",
    ],
    "paths": ["app/auth.py", "app/models.py"],
    "minc": 0.0,
    "limit": 5,
    "q": "save",
    "last": "save",
    "tail": "::save",
    "suffix": "/models.py",
    "path": "app/models.py",
    "ref": "json.dumps",
}
# Values for queries whose rows need a specific class, function or file.
SAMPLE_OVERRIDES: dict[str, dict[str, object]] = {
    "detail._BASES": {"tail": "::User"},
    "detail._SUBCLASSES": {"tail": "::User"},
    "detail._METHODS": {"tail": "::User"},
    "detail._CLASS_TEXT": {"tail": "::User"},
    "detail._CALLEES": {"tail": "::handle", "paths": ["app/api.py"]},
    "detail._CALLERS": {"tail": "::decode_token"},
    "detail._FUNCTION_TEXT": {"tail": "::decode_token"},
    "detail._IMPORTS": {"paths": ["app/api.py"]},
    "references.BY_PATH_AND_TAIL.classes": {"tail": "::User"},
    "references.BY_PATH_AND_TAIL.functions": {"tail": "::User.save"},
    "references._BY_PATH_SUFFIX_AND_TAIL.classes": {"tail": "::User"},
    "references._BY_PATH_SUFFIX_AND_TAIL.functions": {"tail": "::User.save"},
    "references._BY_TAIL.classes": {"tail": "::User"},
    "references._BY_TAIL.functions": {"tail": "::User.save"},
    "references._BY_NAME.classes": {"q": "User"},
    "references._NAME_CONTAINS.classes": {"q": "User"},
    "references._EXTERNAL": {"q": "json.dumps"},
    "search._CLASSES_NAMED": {"last": "User"},
    "search._FILES_WITH_PATH": {"q": "auth"},
}


def _queries_in(name: str, value: object) -> Iterator[tuple[str, Query[object]]]:
    if isinstance(value, Query):
        yield name, value
    elif isinstance(value, DefinitionQueries):
        yield f"{name}.classes", value.classes
        yield f"{name}.functions", value.functions
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _queries_in(f"{name}[{key}]", item)
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            yield from _queries_in(f"{name}[{index}]", item)


def _all_queries() -> list[tuple[str, Query[object]]]:
    """Every query, named ``<module>.<attribute>`` after the module that defines it."""
    found: dict[int, tuple[str, Query[object]]] = {}
    for info in pkgutil.iter_modules(query_package.__path__):
        module = importlib.import_module(f"{query_package.__name__}.{info.name}")
        source = inspect.getsource(module)
        for attr, value in vars(module).items():
            if not re.search(rf"^{re.escape(attr)}\b[^\n]*=", source, re.MULTILINE):
                continue  # imported from another query module, which defines it
            for name, query in _queries_in(f"{info.name}.{attr}", value):
                found.setdefault(id(query), (name, query))
    return sorted(found.values(), key=lambda item: item[0])


def _params(name: str, query: Query[object]) -> dict[str, object]:
    sample = {**SAMPLE_PARAMS, **SAMPLE_OVERRIDES.get(name, {})}
    return {p: sample[p] for p in query.parameters}


QUERIES = _all_queries()


def test_queries_are_collected() -> None:
    assert len(QUERIES) >= 40


def test_every_parameter_has_a_sample() -> None:
    used = {p for _, query in QUERIES for p in query.parameters}
    assert used <= SAMPLE_PARAMS.keys()


@pytest.mark.parametrize(("name", "query"), QUERIES, ids=[name for name, _ in QUERIES])
def test_query_runs_and_decodes(
    name: str, query: Query[object], fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    query.run(fixture_db, fixture_index.repo_root.resolve(), _params(name, query))


def test_every_query_returns_rows(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    # A decoder is only exercised on rows, so every query must return some for its sample.
    root = fixture_index.repo_root.resolve()
    empty = [
        name for name, query in QUERIES if not query.run(fixture_db, root, _params(name, query))
    ]
    assert empty == []


def test_overrides_name_real_queries() -> None:
    assert SAMPLE_OVERRIDES.keys() <= {name for name, _ in QUERIES}


def test_run_rejects_missing_or_extra_parameters(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    query = next(q for _, q in QUERIES if q.parameters == {"limit"})
    root = fixture_index.repo_root
    with pytest.raises(ValueError, match="expects parameters"):
        query.run(fixture_db, root)
    with pytest.raises(ValueError, match="expects parameters"):
        query.run(fixture_db, root, {"limit": 5, "extra": 1})
