"""Vocabulary shared by more than one layer of the engine.

Parsing, resolution, persistence and the query layer all describe the same graph, so
the words they use for it live here, once. This module imports nothing from the package
and sits below every other one. A type used by a single layer belongs in that layer,
e.g. ``query/types.py``.

Enums are ``StrEnum`` so they serialize as their string value and compare equal to it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, TypeAlias


class Language(StrEnum):
    """Supported source languages."""

    PYTHON = "python"


class SymbolKind(StrEnum):
    """Kind of a graph node."""

    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    EXTERNAL = "external"


DefinitionKind: TypeAlias = Literal[SymbolKind.CLASS, SymbolKind.FUNCTION, SymbolKind.METHOD]
"""The ``SymbolKind`` values a parser can extract from a source file."""


class EdgeType(StrEnum):
    """Kind of a graph edge; each value is a relationship table in ``graph/schema.py``."""

    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    INHERITS = "INHERITS"
    CALLS = "CALLS"
    CALLS_EXTERN = "CALLS_EXTERN"


class CallType(StrEnum):
    """How a call resolved to an indexed function; each value writes a ``CALLS`` edge.

    Attributes:
        DIRECT_IMPORT: A bare imported name, or ``self.method()`` on the same class.
        MODULE_ATTR: An attribute of an imported module, e.g. ``auth.verify()``.
        RE_EXPORT: A name re-exported through a package ``__init__.py``.
        MRO: A method inherited from a base class.
    """

    DIRECT_IMPORT = "DIRECT_IMPORT"
    MODULE_ATTR = "MODULE_ATTR"
    RE_EXPORT = "RE_EXPORT"
    MRO = "MRO"


class UnlinkedCall(StrEnum):
    """How a call failed to reach an indexed function; none writes a ``CALLS`` edge.

    Attributes:
        EXTERNAL: Reached a library outside the repo; writes ``CALLS_EXTERN`` instead.
        WILDCARD: Possibly supplied by a ``from x import *``.
        DYNAMIC: Dispatched at runtime, e.g. through ``getattr``.
        CIRCULAR: An import cycle stopped the lookup.
        UNRESOLVED: No rule matched.
    """

    EXTERNAL = "EXTERNAL"
    WILDCARD = "WILDCARD"
    DYNAMIC = "DYNAMIC"
    CIRCULAR = "CIRCULAR"
    UNRESOLVED = "UNRESOLVED"
