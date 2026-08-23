"""The Phase Protocol and IngestContext that flows through phases 0-5.
Enables `compass ingest --stop-after <phase>` for debugging and lets any
phase be unit-tested with a hand-built ctx, no upstream phase required."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from compass_core.graph.writer import WriteResult
from compass_core.ir.graph import ResolvedGraph
from compass_core.ir.models import ParsedFile
from compass_core.progress import ProgressReporter


@dataclass(slots=True)
class FileMetadata:
    path: Path
    language: str
    content_hash: str


@dataclass
class FileManifest:
    files: list[FileMetadata]


@dataclass
class IngestReport:
    resolved_by_language: dict[str, float]
    unresolved_by_language: dict[str, float]
    dangling_import_count: int
    orphan_node_count: int
    degraded_file_count: int


@dataclass
class IngestContext:
    repo_root: Path
    manifest: FileManifest | None = None
    parsed_files: list[ParsedFile] | None = None
    symbol_table: dict[str, str] | None = None
    import_map: dict[str, dict[str, str | None]] | None = None
    resolved_graph: ResolvedGraph | None = None
    report: IngestReport | None = None
    reporter: ProgressReporter | None = None
    write_result: WriteResult | None = None


@runtime_checkable
class Phase(Protocol):
    name: str

    def run(self, ctx: IngestContext) -> IngestContext: ...
