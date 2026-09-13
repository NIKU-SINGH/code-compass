"""Language-agnostic IR — the seam below which no phase may know a specific language.

Definition covers class/function/method (var/interface/struct are future
kinds, added when a language that needs them is registered — do not add
unused kinds speculatively).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DefinitionKind(Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


@dataclass(slots=True)
class Definition:
    id: str  # namespaced, e.g. "py::pkg.mod::Foo" or "py::pkg.mod::Foo.bar"
    kind: DefinitionKind
    name: str
    file_path: str
    line_start: int
    line_end: int
    source: str
    docstring: str | None
    bases: list[str]  # populated for CLASS only
    parent_id: str | None  # populated for METHOD only (id of owning CLASS Definition)
    signature: str | None  # populated for FUNCTION/METHOD only
    decorators: list[str]
    raw_calls: list[str]  # populated for FUNCTION/METHOD only


@dataclass(slots=True)
class ImportStatement:
    module: str
    names: list[str]
    alias: str | None
    is_relative: bool
    is_from: bool
    line: int


@dataclass(slots=True)
class CallSite:
    callee_name: str
    receiver_expr: str | None
    line: int
    enclosing_definition_id: str | None


@dataclass
class ParsedFile:
    path: str
    language: str
    module_name: str
    content_hash: str
    definitions: list[Definition]
    imports: list[ImportStatement]
    call_sites: list[CallSite]
    degraded: bool = False
    error: str | None = None  # human-readable reason when degraded=True


@dataclass(slots=True)
class CallResult:
    """Outcome of resolving one raw call string (Phase 3 / resolution.py).

    Relocated from resolver/call_resolver.py::CallResult, same shape, since
    it's a shared IR-adjacent type this phase produces internally.
    """

    raw: str
    target_id: str | None  # Definition.id if resolved internally
    call_type: str
    confidence: float
    external_library: str | None = None  # set only for EXTERNAL calls
