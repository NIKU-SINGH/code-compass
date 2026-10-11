"""Orchestrates the 6 phases through IngestContext. Enables
`compass ingest --stop-after <phase>` for debugging."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from compass_core.graph.db import GraphDB
from compass_core.graph.schema import create_schema
from compass_core.index.locate import metadata_path_for
from compass_core.index.metadata import IndexMetadata, save_metadata
from compass_core.phases.base import IngestContext, Phase
from compass_core.phases.discovery import DiscoveryPhase
from compass_core.phases.parse import ParsePhase
from compass_core.phases.persistence import PersistencePhase
from compass_core.phases.resolution import ResolutionPhase
from compass_core.phases.symbol_table import SymbolTablePhase
from compass_core.phases.validation import ValidationPhase
from compass_core.progress import ProgressReporter
from compass_core.query.types import Language

logger = logging.getLogger(__name__)

_PHASE_ORDER = ["discovery", "parse", "symbol_table", "resolution", "validation", "persistence"]

_GRAMMAR_PACKAGES: dict[str, str] = {
    "python": "tree-sitter-python",
}


class Pipeline:
    def __init__(self, *, max_workers: int | None = None) -> None:
        self._max_workers = max_workers

    def run(
        self,
        repo_root: Path,
        db_path: Path,
        *,
        reporter: ProgressReporter | None = None,
        stop_after: str | None = None,
        on_phase_complete: Callable[[str, IngestContext], None] | None = None,
    ) -> IngestContext:
        ctx = IngestContext(repo_root=repo_root, reporter=reporter)

        phases: dict[str, Phase] = {
            "discovery": DiscoveryPhase(),
            "parse": ParsePhase(max_workers=self._max_workers),
            "symbol_table": SymbolTablePhase(),
            "resolution": ResolutionPhase(),
            "validation": ValidationPhase(),
        }

        for phase_name in _PHASE_ORDER:
            if phase_name == "persistence":
                break
            ctx = phases[phase_name].run(ctx)
            if on_phase_complete is not None:
                on_phase_complete(phase_name, ctx)
            if stop_after == phase_name:
                return ctx

        db_path.parent.mkdir(parents=True, exist_ok=True)
        building = db_path.with_name(db_path.name + ".building")
        _remove_db(building)
        try:
            with GraphDB(building) as db:
                create_schema(db)
                ctx = PersistencePhase().run(ctx, db)
            os.replace(building, db_path)
        except BaseException:
            _remove_db(building)
            raise
        if on_phase_complete is not None:
            on_phase_complete("persistence", ctx)

        _save_metadata(repo_root, metadata_path_for(db_path))
        return ctx


def _remove_db(path: Path) -> None:
    """Delete a LadybugDB file or directory plus its write-ahead log, if present.

    Args:
        path: The database path; sibling files named ``<path>.wal`` are removed too.
    """
    for candidate in (path, path.with_name(path.name + ".wal")):
        if candidate.is_dir():
            shutil.rmtree(candidate)
        elif candidate.exists():
            candidate.unlink()


def _save_metadata(repo_path: Path, metadata_path: Path) -> None:
    """Write the index metadata (commit, time, grammar versions) via IndexMetadata.

    Args:
        repo_path: Repository root, used for the git commit.
        metadata_path: Destination beside the database (``metadata_path_for``), so
            ``require_index(..., override=db_path)`` finds it; for the default
            database this is ``<repo>/.compass/metadata.json``.
    """
    commit = _get_git_commit(repo_path)
    meta = IndexMetadata(
        indexed_commit=None if commit == "unknown" else commit,
        indexed_at=datetime.now(UTC),
        schema_version=1,
        grammar_versions={Language(k): v for k, v in _grammar_versions().items()},
    )
    save_metadata(metadata_path, meta)
    logger.debug("Metadata written: %s", meta)


def _get_git_commit(repo_path: Path) -> str:
    """Return the HEAD commit hash, or 'unknown' on any failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


def _grammar_versions() -> dict[str, str]:
    """Pin the installed grammar package version for every registered
    language — an unpinned grammar version means incremental diffing would
    trust stale data unknowingly."""
    versions: dict[str, str] = {}
    for language_id, package in _GRAMMAR_PACKAGES.items():
        try:
            versions[language_id] = version(package)
        except PackageNotFoundError:
            continue
    return versions
