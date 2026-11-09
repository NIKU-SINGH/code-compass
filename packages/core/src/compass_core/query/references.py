"""Resolve a user-typed symbol reference to exactly one graph node.

Rules are tried in the order of the query-layer design (section 4.1): exact id, file
path (only when ``allow_file``), fully qualified dotted name, ``path::Name``,
``Class.member`` and bare name. The first rule with any hit decides the outcome: one
hit resolves, several hits are an ``AmbiguousReference``, and no hit at all is a
``SymbolNotFound`` with substring suggestions. A reference is never guessed.

The graph stores public ids, repo-relative paths and qualified names, so an exact id,
a file path and a qualified name are equality matches; only the partial rules
(``path::Name`` with a partial path, ``Class.member``) match on a suffix. User input
only ever reaches Cypher as a ``$parameter``; the only text composed into a query is
the constant ``WHERE`` conditions below, at import.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from compass_core.contract.models import SymbolRef
from compass_core.contract.results import AmbiguousReference, Lookup, SymbolNotFound
from compass_core.contract.types import MatchRule
from compass_core.graph.db import GraphDB, QueryParams
from compass_core.query.cypher import Query
from compass_core.query.rows import (
    CLASS_FIELDS,
    FILE_FIELDS,
    FUNCTION_FIELDS,
    class_from_row,
    columns,
    count_value,
    external_from_row,
    file_from_row,
    function_from_row,
    text_value,
)
from compass_core.shared_types import SymbolKind

_SEP = "::"
_MAX_SUGGESTIONS = 5


@dataclass(frozen=True, slots=True)
class DefinitionQueries:
    """The class and the function query for one definition filter over node ``n``.

    Attributes:
        classes: Matching classes.
        functions: Matching functions and methods.

    Example:
        ``_BY_NAME.functions.run(db, {"q": "save"})`` returns both ``save`` methods.
    """

    classes: Query[SymbolRef]
    functions: Query[SymbolRef]


def _definitions_where(condition: str) -> DefinitionQueries:
    """Build the query pair for a constant ``WHERE`` condition (module load time only)."""
    return DefinitionQueries(
        classes=Query(
            f"MATCH (n:Class) WHERE {condition} RETURN {columns('n', CLASS_FIELDS)}",
            class_from_row,
        ),
        functions=Query(
            f"MATCH (n:Function) WHERE {condition} RETURN {columns('n', FUNCTION_FIELDS)}",
            function_from_row,
        ),
    )


_BY_ID = _definitions_where("n.id = $id")
_BY_ID_OR_ID_SUFFIX = _definitions_where("n.id = $id OR n.id ENDS WITH $suffix")
_BY_QUALIFIED_NAME = _definitions_where("n.qualified_name = $q")
_BY_TAIL = _definitions_where("n.id ENDS WITH $tail")
_BY_NAME = _definitions_where("n.name = $q")
_NAME_CONTAINS = _definitions_where("lower(n.name) CONTAINS lower($q)")

FILES_AT_PATHS: Query[SymbolRef] = Query(
    f"MATCH (f:File) WHERE f.path IN $paths RETURN {columns('f', FILE_FIELDS)}",
    file_from_row,
)
"""Files whose repo-relative path is one of ``$paths``."""
_EXTERNAL: Query[SymbolRef] = Query(
    "MATCH (e:ExternalFunction) WHERE e.full_ref = $q RETURN e.full_ref, e.name",
    external_from_row,
)
_FAN_IN: Query[tuple[str, int]] = Query(
    """
    MATCH (c:Function)-[:CALLS]->(f:Function) WHERE f.id IN $ids
    RETURN f.id, count(c)
    """,
    lambda row: (text_value(row[0], "id"), count_value(row[1])),
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedReference:
    """A reference that resolved to exactly one symbol.

    Attributes:
        symbol: The resolved symbol.
        rule: The resolution rule that matched.

    Example:
        ``resolve(db, "User.save", repo_root=root)`` returns
        ``ResolvedReference(symbol=<app/models.py::User.save>, rule=MatchRule.CLASS_MEMBER)``.
    """

    symbol: SymbolRef
    rule: MatchRule


def _definitions(db: GraphDB, queries: DefinitionQueries, params: QueryParams) -> list[SymbolRef]:
    """Classes, then functions and methods, matching one definition filter."""
    return queries.classes.run(db, params) + queries.functions.run(db, params)


def _normalize_path(text: str, repo_root: Path) -> str:
    """Make an absolute path under ``repo_root`` relative; leave anything else alone."""
    path = Path(text)
    if path.is_absolute():
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return text
    return text.removeprefix("./")


def _file(db: GraphDB, path: str) -> list[SymbolRef]:
    return FILES_AT_PATHS.run(db, {"paths": [path]})


def _exact_id(db: GraphDB, ref: str, repo_root: Path, allow_file: bool) -> list[SymbolRef]:
    if ref.startswith("ext" + _SEP):
        return _EXTERNAL.run(db, {"q": ref.removeprefix("ext" + _SEP)})
    if ref.startswith("file" + _SEP):
        return _file(db, ref.removeprefix("file" + _SEP)) if allow_file else []
    if _SEP not in ref:
        return []
    path, tail = ref.rsplit(_SEP, 1)
    return _definitions(db, _BY_ID, {"id": f"{_normalize_path(path, repo_root)}{_SEP}{tail}"})


def _qualified(db: GraphDB, ref: str) -> list[SymbolRef]:
    """Match a stored qualified name, ``module.[Class.]name``, exactly."""
    return _definitions(db, _BY_QUALIFIED_NAME, {"q": ref})


def _path_and_name(db: GraphDB, ref: str, repo_root: Path) -> list[SymbolRef]:
    """``path::Name`` where ``path`` is the file's path or a trailing part of it."""
    path, tail = ref.rsplit(_SEP, 1)
    exact = f"{_normalize_path(path, repo_root)}{_SEP}{tail}"
    return _definitions(db, _BY_ID_OR_ID_SUFFIX, {"id": exact, "suffix": "/" + exact})


def _class_member(db: GraphDB, ref: str) -> list[SymbolRef]:
    return _definitions(db, _BY_TAIL, {"tail": _SEP + ref})


def _bare_name(db: GraphDB, ref: str) -> list[SymbolRef]:
    return _definitions(db, _BY_NAME, {"q": ref})


def _hits(
    db: GraphDB, rule: MatchRule, text: str, repo_root: Path, allow_file: bool
) -> list[SymbolRef]:
    """Symbols matching ``text`` under one rule; empty when the rule does not apply."""
    plain = _SEP not in text
    if rule is MatchRule.EXACT_ID:
        return _exact_id(db, text, repo_root, allow_file)
    if rule is MatchRule.FILE_PATH:
        return _file(db, _normalize_path(text, repo_root)) if allow_file else []
    if rule is MatchRule.QUALIFIED_NAME:
        return _qualified(db, text) if plain and "." in text else []
    if rule is MatchRule.PATH_AND_NAME:
        return _path_and_name(db, text, repo_root) if not plain else []
    if rule is MatchRule.CLASS_MEMBER:
        return _class_member(db, text) if plain and "." in text else []
    return _bare_name(db, text) if plain else []


def _fan_in(db: GraphDB, symbols: Sequence[SymbolRef]) -> dict[str, int]:
    """Incoming ``CALLS`` count per function or method (one query); others count zero."""
    ids = [s.id for s in symbols if s.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD)]
    return dict(_FAN_IN.run(db, {"ids": ids})) if ids else {}


def _suggestions(db: GraphDB, text: str) -> tuple[SymbolRef, ...]:
    if not text:
        return ()
    found = _definitions(db, _NAME_CONTAINS, {"q": text})
    found.sort(key=lambda s: (s.name.lower() != text.lower(), len(s.name), s.id))
    return tuple(found[:_MAX_SUGGESTIONS])


def resolve(
    db: GraphDB, ref: str, *, repo_root: Path, allow_file: bool = False
) -> Lookup[ResolvedReference]:
    """Resolve a symbol reference using the first rule that has any hit.

    Args:
        db: Open graph database.
        ref: User-typed reference: public id, file path, dotted name, ``path::Name``,
            ``Class.member`` or bare name.
        repo_root: Absolute repository root; an absolute path in ``ref`` is made
            relative to it.
        allow_file: Whether a file path (rule 2) is acceptable for this operation.

    Returns:
        A ``ResolvedReference`` for a single match, an ``AmbiguousReference`` listing
        the candidates (most incoming calls first) when several symbols matched the
        same rule, or a ``SymbolNotFound`` with up to five suggestions.

    Raises:
        IndexIncompatibleError: A stored row does not have the expected shape.

    Example:
        ``resolve(db, "app/auth.py::decode_token", repo_root=root)`` returns
        ``ResolvedReference(symbol=<decode_token>, rule=MatchRule.EXACT_ID)``.
    """
    text = ref.strip()
    if text:
        for rule in MatchRule:
            found = _hits(db, rule, text, repo_root, allow_file)
            if len(found) == 1:
                return ResolvedReference(symbol=found[0], rule=rule)
            if found:
                fan_in = _fan_in(db, found)
                ordered = sorted(found, key=lambda s: (-fan_in.get(s.id, 0), s.id))
                return AmbiguousReference(reference=ref, candidates=tuple(ordered))
    return SymbolNotFound(reference=ref, suggestions=_suggestions(db, text))
