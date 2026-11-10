"""The ids the graph stores for classes and functions: the public ids queries return.

Parsing and resolution key definitions by an internal, language-namespaced id
(``py::app.models::User.save``). The graph stores the public id instead
(``app/models.py::User.save``), plus the dotted qualified name, so every lookup by a
public id is a primary-key match and no reader has to translate between the two.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from compass_core.ir.graph import ResolvedGraph
from compass_core.ir.models import Definition

SEP = "::"
"""Separator between a public id's file path and its ``[Class.]name`` tail."""


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredGraph:
    """A resolved graph re-keyed by public ids, ready to write.

    Attributes:
        graph: The graph with every definition id and edge endpoint replaced by its
            public id. File paths and external references are unchanged.
        qualified_names: Dotted qualified name of every definition, by public id.

    Example:
        ``class User`` with method ``save`` in ``app/models.py`` gives definitions with ids
        ``"app/models.py::User"`` and ``"app/models.py::User.save"``, and
        ``qualified_names["app/models.py::User.save"] == "app.models.User.save"``.
    """

    graph: ResolvedGraph
    qualified_names: Mapping[str, str]


def _module_from_path(file_path: str) -> str:
    parts = list(PurePosixPath(file_path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def public_id(definition: Definition) -> str:
    """The public id of a definition: ``<repo-relative path>::<[Class.]name>``.

    Args:
        definition: A parsed class, function or method.

    Returns:
        The public id.

    Example:
        ``User.save`` in ``app/models.py`` (internal id ``py::app.models::User.save``)
        gives ``"app/models.py::User.save"``.
    """
    return f"{definition.file_path}{SEP}{definition.id.rsplit(SEP, 1)[-1]}"


def qualified_name(definition: Definition) -> str:
    """The dotted qualified name of a definition: module plus ``[Class.]name``.

    Args:
        definition: A parsed class, function or method.

    Returns:
        The qualified name; the module comes from the internal id, or from the file
        path when the id carries none.

    Example:
        ``User.save`` in ``app/models.py`` gives ``"app.models.User.save"``.
    """
    head, _, tail = definition.id.rpartition(SEP)
    module = head.split(SEP, 1)[1] if SEP in head else _module_from_path(definition.file_path)
    return f"{module}.{tail}" if module else tail


def with_stored_ids(graph: ResolvedGraph) -> StoredGraph:
    """Re-key a resolved graph by public ids.

    Edge endpoints that are not definitions of the graph keep their value, so they
    still match no node and are dropped by the writer, as before.

    Args:
        graph: The graph produced by resolution.

    Returns:
        A copy with public ids, and the qualified name of every definition.

    Example:
        A ``CallEdge(caller_id="py::app.api::handle", callee_id="py::app.auth::parse")``
        becomes ``CallEdge(caller_id="app/api.py::handle", callee_id="app/auth.py::parse")``.
    """
    definitions = [d for f in graph.files for d in f.definitions]
    ids = {d.id: public_id(d) for d in definitions}

    def new(old: str) -> str:
        return ids.get(old, old)

    files = [
        replace(
            f,
            definitions=[
                replace(
                    d, id=new(d.id), parent_id=None if d.parent_id is None else new(d.parent_id)
                )
                for d in f.definitions
            ],
        )
        for f in graph.files
    ]
    return StoredGraph(
        graph=ResolvedGraph(
            files=files,
            call_edges=[
                replace(e, caller_id=new(e.caller_id), callee_id=new(e.callee_id))
                for e in graph.call_edges
            ],
            external_call_edges=[
                replace(e, caller_id=new(e.caller_id)) for e in graph.external_call_edges
            ],
            import_edges=list(graph.import_edges),
            inherit_edges=[
                replace(e, child_id=new(e.child_id), parent_id=new(e.parent_id))
                for e in graph.inherit_edges
            ],
        ),
        qualified_names={ids[d.id]: qualified_name(d) for d in definitions},
    )
