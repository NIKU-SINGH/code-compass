"""Resolved call/import/inheritance graph — Phase 3 output, Phase 5 input.

Edge shapes are kept as four distinct dataclasses (not collapsed into one
generic Edge type) because call_resolver's 10 prioritized resolution rules
carry different fields per edge kind (external edges have no callee_id,
only a full_ref + library) and collapsing would lose that without gaining
anything — this mirrors resolver/models.py exactly, just relocated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from compass_core.ir.models import ParsedFile
from compass_core.shared_types import CallType, UnlinkedCall

CONFIDENCE: dict[CallType | UnlinkedCall, float] = {
    CallType.DIRECT_IMPORT: 1.0,
    CallType.MODULE_ATTR: 0.9,
    CallType.RE_EXPORT: 0.8,
    CallType.MRO: 0.8,
    UnlinkedCall.WILDCARD: 0.6,
    UnlinkedCall.DYNAMIC: 0.0,
    UnlinkedCall.CIRCULAR: 0.0,
    UnlinkedCall.EXTERNAL: 0.0,
    UnlinkedCall.UNRESOLVED: 0.0,
}


@dataclass(slots=True)
class CallEdge:
    caller_id: str
    callee_id: str
    call_type: CallType
    confidence: float
    line: int = 0


@dataclass(slots=True)
class ExternalCallEdge:
    caller_id: str
    full_ref: str
    library: str
    line: int = 0


@dataclass(slots=True)
class ImportEdge:
    from_path: str
    to_path: str


@dataclass(slots=True)
class InheritEdge:
    child_id: str
    parent_id: str


@dataclass
class ResolvedGraph:
    files: list[ParsedFile] = field(default_factory=list)
    call_edges: list[CallEdge] = field(default_factory=list)
    external_call_edges: list[ExternalCallEdge] = field(default_factory=list)
    import_edges: list[ImportEdge] = field(default_factory=list)
    inherit_edges: list[InheritEdge] = field(default_factory=list)
