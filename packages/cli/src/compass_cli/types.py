"""Typed data objects shared across compass_cli commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from compass_core.shared_types import Language


@dataclass(frozen=True)
class IngestSummary:
    """Aggregate results of a single `compass ingest` run."""

    file_count: int
    class_count: int
    function_count: int
    elapsed: float
    node_count: int
    edge_count: int
    db_path: Path
    db_size: int
    skipped: int
    resolved_pct: float
    orphan_count: int
    language_counts: dict[Language, int]
    dropped_edges: int = 0


class OutputFormat(StrEnum):
    """How a query command prints its answer.

    Attributes:
        TEXT: Compact text, one line per item with ``file:line`` first; for people and
            coding agents.
        JSON: The typed contract result as JSON; for scripts and tools.
    """

    TEXT = "text"
    JSON = "json"
