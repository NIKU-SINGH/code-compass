"""Typed Cypher queries: each statement lives next to the decoder for its rows.

A ``Query`` is defined once, at module level, with its full Cypher text. Running it
returns typed values instead of raw rows, so no caller indexes a row by position, and
the ``$parameters`` a statement uses are checked against the ones supplied.

User text only ever reaches Cypher as a ``$parameter``. Statements may be composed
from the column lists in ``query/rows.py`` when the module is imported, never per call.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from compass_core.graph.db import GraphDB, QueryParams, Row, as_rows

T = TypeVar("T")

_PARAMETER = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True, slots=True)
class Query(Generic[T]):
    """A Cypher statement and the decoder for one of its result rows.

    Attributes:
        cypher: The full statement. User input appears only as ``$name`` parameters.
        decode: Turns one result row into a typed value.
        parameters: Names of the ``$parameters`` the statement uses, derived from
            ``cypher``.

    Example:
        ``FILE_PATHS = Query("MATCH (f:File) RETURN f.path", lambda row: text_value(row[0],
        "path"))`` makes ``FILE_PATHS.run(db)`` return ``["app/auth.py", ...]``.
    """

    cypher: str
    decode: Callable[[Row], T]
    parameters: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", frozenset(_PARAMETER.findall(self.cypher)))

    def run(self, db: GraphDB, params: Mapping[str, object] | None = None) -> list[T]:
        """Execute the statement and decode every row.

        Args:
            db: Open graph database.
            params: A value for every ``$parameter`` of the statement, and nothing else.

        Returns:
            One decoded value per result row, in result order.

        Raises:
            ValueError: ``params`` does not name exactly the statement's parameters. This
                is a bug in the query layer, never caused by user input.
            IndexIncompatibleError: A row does not have the shape the decoder expects.

        Example:
            ``ENTRY_POINTS.run(db, {"limit": 5})`` returns up to five file symbols.
        """
        supplied: QueryParams = dict(params or {})
        if supplied.keys() != self.parameters:
            raise ValueError(
                f"query expects parameters {sorted(self.parameters)}, got {sorted(supplied)}"
            )
        result = db.execute(self.cypher, supplied) if supplied else db.execute(self.cypher)
        rows = as_rows(result)
        return [self.decode(row) for row in rows]

    def first(self, db: GraphDB, params: Mapping[str, object] | None = None) -> T | None:
        """Like ``run`` but return only the first decoded row, or ``None`` when empty.

        Args:
            db: Open graph database.
            params: A value for every ``$parameter`` of the statement, and nothing else.

        Returns:
            The first decoded value, or ``None`` if the statement returned no rows.

        Raises:
            ValueError: ``params`` does not name exactly the statement's parameters.
            IndexIncompatibleError: The row does not have the shape the decoder expects.

        Example:
            ``FUNCTION_COUNT.first(db)`` returns ``412`` on a repo with 412 functions.
        """
        found = self.run(db, params)
        return found[0] if found else None
