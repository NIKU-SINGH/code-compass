"""Data models for the resolved knowledge graph.

After pass 1 (parsing), we have raw ParsedFile objects with unresolved call
strings. After the resolver runs, we have a ResolvedGraph — a flat structure
of nodes (still ParsedFile) and typed, confidence-scored edges ready for the
writer to persist verbatim.

The writer receives a ResolvedGraph and makes zero semantic decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from compass_core.parser.models import ParsedFile

# ---------------------------------------------------------------------------
# Call Resolution Types and Confidence Scores
# ---------------------------------------------------------------------------

"""Call resolution type constants and their associated confidence scores.

- RESOLVED: Direct import match (1.0)
- POLYMORPHIC: Resolved via MRO / base class (0.8)
- WILDCARD: from x import * (0.6)
- DYNAMIC: getattr / dynamic dispatch (0.0)
- EXTERNAL: Library not in the indexed repo (n/a)
- CIRCULAR: Import cycle detected (0.0)
- UNRESOLVED: Catch-all fallback (0.0)
"""

RESOLVED = "RESOLVED"
POLYMORPHIC = "POLYMORPHIC"
WILDCARD = "WILDCARD"
DYNAMIC = "DYNAMIC"
EXTERNAL = "EXTERNAL"
CIRCULAR = "CIRCULAR"
UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------


@dataclass
class CallEdge:
    """A resolved internal function-to-function call.

    Attributes:
        caller_id: The unique ID of the calling function node.
        callee_id: The unique ID of the target function node.
        call_type: The type of resolution (e.g., RESOLVED, POLYMORPHIC).
        confidence: A score from 0.0 to 1.0 indicating resolution certainty.
        line: The 1-indexed line number where the call occurs.

    Example:
        ```python
        # Code: foo() -> bar() at line 42
        edge = CallEdge(
            caller_id="pkg.module.foo",
            callee_id="pkg.other.bar",
            call_type=RESOLVED,
            confidence=1.0,
            line=42
        )
        ```
    """

    caller_id: str
    callee_id: str
    call_type: str
    confidence: float
    line: int = 0


@dataclass
class ExternalCallEdge:
    """A call to a function in an external (non-indexed) library.

    Attributes:
        caller_id: The unique ID of the calling function node.
        full_ref: The fully qualified reference to the library function (e.g., "requests.get").
        library: The top-level module name of the external library (e.g., "requests").
        line: The 1-indexed line number where the call occurs.

    Example:
        ```python
        # Code: requests.get() at line 10
        edge = ExternalCallEdge(
            caller_id="my_app.main",
            full_ref="requests.get",
            library="requests",
            line=10
        )
        ```
    """

    caller_id: str
    full_ref: str
    library: str
    line: int = 0


@dataclass
class ImportEdge:
    """A file-level import dependency.

    Attributes:
        from_path: The workspace-relative path of the importing file.
        to_path: The workspace-relative path of the imported file.

    Example:
        ```python
        # In main.py: import utils
        edge = ImportEdge(
            from_path="src/main.py",
            to_path="src/utils.py"
        )
        ```
    """

    from_path: str
    to_path: str


@dataclass
class InheritEdge:
    """A class inheritance relationship.

    Attributes:
        child_id: The unique ID of the subclass node.
        parent_id: The unique ID of the superclass node.

    Example:
        ```python
        # Code: class MyView(BaseView):
        edge = InheritEdge(
            child_id="myapp.views.MyView",
            parent_id="myapp.base.BaseView"
        )
        ```
    """

    child_id: str
    parent_id: str


# ---------------------------------------------------------------------------
# Resolved graph — the writer's input contract
# ---------------------------------------------------------------------------


@dataclass
class ResolvedGraph:
    """Fully resolved knowledge graph, ready for DB persistence.

    The writer consumes this graph and persists it to the database with zero
    semantic transformation.

    Attributes:
        files: A list of all successfully parsed high-level file models.
        call_edges: A list of resolved internal function-to-function calls.
        external_call_edges: A list of calls to external library functions.
        import_edges: A list of file-level import dependencies.
        inherit_edges: A list of class inheritance relationships.

    Example:
        ```python
        graph = ResolvedGraph(
            files=[parsed_file_1, parsed_file_2],
            call_edges=[edge_1],
            import_edges=[import_edge_1]
        )
        ```
    """

    files: list[ParsedFile] = field(default_factory=list)
    call_edges: list[CallEdge] = field(default_factory=list)
    external_call_edges: list[ExternalCallEdge] = field(default_factory=list)
    import_edges: list[ImportEdge] = field(default_factory=list)
    inherit_edges: list[InheritEdge] = field(default_factory=list)
