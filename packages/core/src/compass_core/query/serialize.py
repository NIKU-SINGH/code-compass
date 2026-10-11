"""JSON serialization of query results via cached Pydantic ``TypeAdapter``s.

Models stay plain dataclasses; Pydantic is used only here, at the adapter edge.
Enums serialize as their value, ``datetime`` as ISO-8601, ``Path`` as a string and
tuples / frozensets as arrays.
"""

from __future__ import annotations

from pydantic import TypeAdapter

from compass_core.query.errors import ErrorResponse
from compass_core.query.results import (
    AmbiguousReference,
    ImpactResult,
    NodeDetail,
    OverviewResult,
    SearchResult,
    SymbolNotFound,
)

Serializable = (
    SearchResult
    | ImpactResult
    | OverviewResult
    | NodeDetail
    | AmbiguousReference
    | SymbolNotFound
    | ErrorResponse
)


_ADAPTERS: dict[type[object], TypeAdapter[object]] = {}


def _adapter_for(obj: Serializable) -> TypeAdapter[object]:
    tp: type[object] = type(obj)
    adapter = _ADAPTERS.get(tp)
    if adapter is None:
        adapter = _ADAPTERS[tp] = TypeAdapter(tp)
    return adapter


def to_json(obj: Serializable) -> str:
    """Serialize a query result, reference outcome or error envelope to JSON.

    Args:
        obj: The value to serialize.

    Returns:
        A compact JSON string.

    Example:
        ``to_json(SymbolNotFound(reference="x", suggestions=()))`` returns
        ``'{"outcome":"not_found","reference":"x","suggestions":[]}'``.
    """
    return _adapter_for(obj).dump_json(obj).decode()
