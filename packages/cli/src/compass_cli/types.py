"""Typed data objects shared across compass_cli commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
