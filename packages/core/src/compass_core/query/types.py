"""Closed vocabularies and identifier types private to the query layer.

Enums are ``StrEnum`` so they serialize as their string value. Identifiers are
``NewType`` over ``str`` so a file path cannot be passed where a symbol id is expected.
Vocabulary shared with parsing and persistence lives in ``compass_core/shared_types.py``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import NewType

SymbolId = NewType("SymbolId", str)
"""Public node id, e.g. ``"packages/core/src/compass_core/graph/writer.py::write"``."""

RepoPath = NewType("RepoPath", str)
"""Repo-relative POSIX path, e.g. ``"packages/core/src/compass_core/graph/writer.py"``."""

QualifiedName = NewType("QualifiedName", str)
"""Dotted qualified name, e.g. ``"compass_core.graph.writer.write"``."""


class ViaKind(StrEnum):
    """Relationship through which a node was reached."""

    CALLS = "CALLS"
    CALLED_BY = "CALLED_BY"
    IMPORTS = "IMPORTS"
    IMPORTED_BY = "IMPORTED_BY"
    INHERITS = "INHERITS"
    INHERITED_BY = "INHERITED_BY"
    OVERRIDES = "OVERRIDES"
    CONTAINED_IN = "CONTAINED_IN"


class MatchRule(StrEnum):
    """Symbol resolution rules, in the order they are tried."""

    EXACT_ID = "EXACT_ID"
    FILE_PATH = "FILE_PATH"
    QUALIFIED_NAME = "QUALIFIED_NAME"
    PATH_AND_NAME = "PATH_AND_NAME"
    CLASS_MEMBER = "CLASS_MEMBER"
    BARE_NAME = "BARE_NAME"


class SearchMatch(StrEnum):
    """How a search hit matched the query."""

    EXACT = "EXACT"
    QUALIFIED_SUFFIX = "QUALIFIED_SUFFIX"
    PREFIX = "PREFIX"
    SUBSTRING = "SUBSTRING"


class Operation(StrEnum):
    """Query operations exposed by the engine."""

    FIND = "FIND"
    DESCRIBE = "DESCRIBE"
    CALLERS = "CALLERS"
    CALLEES = "CALLEES"
    IMPACT = "IMPACT"
    CALL_PATH = "CALL_PATH"
    OUTLINE = "OUTLINE"
    HIERARCHY = "HIERARCHY"
    EXTERNAL_USAGE = "EXTERNAL_USAGE"
    STATUS = "STATUS"
    OVERVIEW = "OVERVIEW"
    SOURCE = "SOURCE"
    GRAPH_MAP = "GRAPH_MAP"
    NEIGHBORHOOD = "NEIGHBORHOOD"


class Outcome(StrEnum):
    """JSON discriminator for a query result."""

    OK = "ok"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


class CaveatCode(StrEnum):
    """Reasons an answer may be incomplete."""

    STALE_INDEX = "STALE_INDEX"
    UNRESOLVED_CALLS = "UNRESOLVED_CALLS"
    DEGRADED_FILES = "DEGRADED_FILES"
    TRUNCATED = "TRUNCATED"
    DEPTH_LIMIT_REACHED = "DEPTH_LIMIT_REACHED"
