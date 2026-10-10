"""Resolve a user-typed symbol reference to exactly one graph node.

Rules are tried in the order of the query-layer design (section 4.1): exact id, file
path (only when ``allow_file``), fully qualified dotted name, ``path::Name``,
``Class.member`` and bare name. The first rule with any hit decides the outcome: one
hit resolves, several hits are an ``AmbiguousReference``, and no hit at all is a
``SymbolNotFound`` with substring suggestions. A reference is never guessed.

Public ids are repo-relative; the graph stores ``py::<module>::<tail>`` ids with
``file_path`` columns. User input only ever reaches Cypher as a ``$parameter``; the
only text interpolated into a query is the constant ``WHERE`` templates below.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from compass_core.graph.db import GraphDB, QueryParams, as_rows
from compass_core.query.models import SymbolRef
from compass_core.query.results import AmbiguousReference, Lookup, SymbolNotFound
from compass_core.query.rows import (
    count_value,
    external_from_row,
    file_from_row,
    is_method_flag,
    symbol_from_row,
)
from compass_core.query.types import MatchRule, SymbolKind

_SEP = "::"
_MAX_SUGGESTIONS = 5
_FUNCTION_QUERY = (
    "MATCH (n:Function) WHERE {where} "
    "RETURN n.id, n.name, n.file_path, n.line_start, n.line_end, n.signature, n.is_method"
)
_CLASS_QUERY = (
    "MATCH (n:Class) WHERE {where} "
    "RETURN n.id, n.name, n.file_path, n.line_start, n.line_end, '' AS signature"
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


def _definitions(db: GraphDB, where: str, params: QueryParams, repo_root: Path) -> list[SymbolRef]:
    """Classes and functions satisfying a constant ``where`` template over node ``n``."""
    classes = [
        symbol_from_row(r, SymbolKind.CLASS, repo_root)
        for r in as_rows(db.execute(_CLASS_QUERY.format(where=where), params))
    ]
    functions = [
        symbol_from_row(
            r, SymbolKind.METHOD if is_method_flag(r[6]) else SymbolKind.FUNCTION, repo_root
        )
        for r in as_rows(db.execute(_FUNCTION_QUERY.format(where=where), params))
    ]
    return classes + functions


def _stored_paths(rel: str, repo_root: Path) -> list[str]:
    """Both spellings of a repo-relative path: as given and joined onto ``repo_root``."""
    return [rel, (repo_root / rel).as_posix()]


def _normalize_path(text: str, repo_root: Path) -> str:
    """Make an absolute path under ``repo_root`` relative; leave anything else alone."""
    path = Path(text)
    if path.is_absolute():
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return text
    return text.removeprefix("./")


def _by_path_and_tail(
    db: GraphDB, path: str, tail: str, repo_root: Path, *, suffix: bool
) -> list[SymbolRef]:
    """Definitions in ``path`` (or any file whose path ends with it) named ``tail``."""
    where = "(n.file_path IN $paths" + (" OR n.file_path ENDS WITH $suffix)" if suffix else ")")
    params: QueryParams = {
        "paths": _stored_paths(path, repo_root),
        "suffix": "/" + path,
        "tail": _SEP + tail,
    }
    return _definitions(db, where + " AND n.id ENDS WITH $tail", params, repo_root)


def _file(db: GraphDB, path: str, repo_root: Path) -> list[SymbolRef]:
    rows = as_rows(
        db.execute(
            "MATCH (f:File) WHERE f.path IN $paths RETURN f.path, f.module_name",
            {"paths": _stored_paths(path, repo_root)},
        )
    )
    return [file_from_row(r, repo_root) for r in rows]


def _external(db: GraphDB, full_ref: str) -> list[SymbolRef]:
    rows = as_rows(
        db.execute(
            "MATCH (e:ExternalFunction) WHERE e.full_ref = $q RETURN e.full_ref, e.name",
            {"q": full_ref},
        )
    )
    return [external_from_row(r) for r in rows]


def _exact_id(db: GraphDB, ref: str, repo_root: Path, allow_file: bool) -> list[SymbolRef]:
    if ref.startswith("ext" + _SEP):
        return _external(db, ref.removeprefix("ext" + _SEP))
    if ref.startswith("file" + _SEP):
        return _file(db, ref.removeprefix("file" + _SEP), repo_root) if allow_file else []
    if _SEP not in ref:
        return []
    path, tail = ref.rsplit(_SEP, 1)
    return _by_path_and_tail(db, _normalize_path(path, repo_root), tail, repo_root, suffix=False)


def _qualified(db: GraphDB, ref: str, repo_root: Path) -> list[SymbolRef]:
    """Match ``module.[Class.]name`` by trying every module/tail split of the dotted name."""
    parts = ref.split(".")
    ids = [
        f"py{_SEP}{'.'.join(parts[:i])}{_SEP}{'.'.join(parts[i:])}" for i in range(1, len(parts))
    ]
    return _definitions(db, "n.id IN $ids", {"ids": ids}, repo_root)


def _path_and_name(db: GraphDB, ref: str, repo_root: Path) -> list[SymbolRef]:
    path, tail = ref.rsplit(_SEP, 1)
    return _by_path_and_tail(db, _normalize_path(path, repo_root), tail, repo_root, suffix=True)


def _class_member(db: GraphDB, ref: str, repo_root: Path) -> list[SymbolRef]:
    return _definitions(db, "n.id ENDS WITH $tail", {"tail": _SEP + ref}, repo_root)


def _bare_name(db: GraphDB, ref: str, repo_root: Path) -> list[SymbolRef]:
    return _definitions(db, "n.name = $q", {"q": ref}, repo_root)


def _hits(
    db: GraphDB, rule: MatchRule, text: str, repo_root: Path, allow_file: bool
) -> list[SymbolRef]:
    """Symbols matching ``text`` under one rule; empty when the rule does not apply."""
    plain = _SEP not in text
    if rule is MatchRule.EXACT_ID:
        return _exact_id(db, text, repo_root, allow_file)
    if rule is MatchRule.FILE_PATH:
        return _file(db, _normalize_path(text, repo_root), repo_root) if allow_file else []
    if rule is MatchRule.QUALIFIED_NAME:
        return _qualified(db, text, repo_root) if plain and "." in text else []
    if rule is MatchRule.PATH_AND_NAME:
        return _path_and_name(db, text, repo_root) if not plain else []
    if rule is MatchRule.CLASS_MEMBER:
        return _class_member(db, text, repo_root) if plain and "." in text else []
    return _bare_name(db, text, repo_root) if plain else []


def _fan_in(db: GraphDB, symbols: Sequence[SymbolRef], repo_root: Path) -> dict[str, int]:
    """Incoming ``CALLS`` count per function or method; other kinds are absent (zero)."""
    counts: dict[str, int] = {}
    for symbol in symbols:
        if symbol.kind not in (SymbolKind.FUNCTION, SymbolKind.METHOD) or not symbol.file_path:
            continue
        rows = as_rows(
            db.execute(
                "MATCH (c:Function)-[:CALLS]->(f:Function) "
                "WHERE f.file_path IN $paths AND f.id ENDS WITH $tail RETURN count(c)",
                {
                    "paths": _stored_paths(symbol.file_path, repo_root),
                    "tail": _SEP + symbol.id.rsplit(_SEP, 1)[1],
                },
            )
        )
        counts[symbol.id] = count_value(rows[0][0]) if rows else 0
    return counts


def _suggestions(db: GraphDB, text: str, repo_root: Path) -> tuple[SymbolRef, ...]:
    if not text:
        return ()
    found = _definitions(db, "lower(n.name) CONTAINS lower($q)", {"q": text}, repo_root)
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
        repo_root: Absolute repository root; public ids are relative to it.
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
                fan_in = _fan_in(db, found, repo_root)
                ordered = sorted(found, key=lambda s: (-fan_in.get(s.id, 0), s.id))
                return AmbiguousReference(reference=ref, candidates=tuple(ordered))
    return SymbolNotFound(reference=ref, suggestions=_suggestions(db, text, repo_root))
