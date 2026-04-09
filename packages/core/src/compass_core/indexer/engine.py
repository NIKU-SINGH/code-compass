"""Orchestrates the three-phase indexing pipeline.

Usage
-----
    from pathlib import Path
    from compass_core.indexer.engine import index_repo

    result = index_repo(Path("/path/to/repo"))
    print(result.file_count, result.class_count, result.function_count)

Phase 1 — Parse (parallel, CPU-bound)
--------------------------------------
  Walk the repo with file_walker. Parse each .py file with tree-sitter
  inside a ProcessPoolExecutor. Each worker creates its own fresh Parser.
  Failures are logged and skipped without aborting the run.

Phase 2 — Resolve (sequential, in-memory)
------------------------------------------
  Build symbol table and import map from all ParsedFile objects, then
  resolve every raw call into a typed, confidence-scored edge. Produces
  a ResolvedGraph with no unresolved strings remaining.

Phase 3 — Write (sequential, DB)
----------------------------------
  Ensure the LadybugDB schema exists. Write all nodes first, then all
  edges. The writer makes zero semantic decisions — it is a pure sink.

After all phases, .compass/metadata.json is written with indexed_commit
and indexed_at for incremental-indexing prep.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from compass_core.graph.db import GraphDB
from compass_core.graph.schema import create_schema
from compass_core.graph.writer import write
from compass_core.parser.extractor import extract_file
from compass_core.parser.file_walker import walk_python_files
from compass_core.parser.models import ParsedFile
from compass_core.progress import ProgressReporter
from compass_core.resolver.resolver import resolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class IndexResult:
    """Summary statistics from a completed index run.

    Attributes:
        file_count: Number of files successfully parsed.
        class_count: Total number of classes found across all files.
        function_count: Total number of functions and methods found.
        elapsed_seconds: Total time taken for the indexing process.

    Example:
        >>> result = IndexResult(
        ...     file_count=10,
        ...     class_count=5,
        ...     function_count=20,
        ...     elapsed_seconds=1.5
        ... )
        >>> print(result.file_count)
        10
    """

    file_count: int
    class_count: int
    function_count: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def index_repo(
    repo_path: Path,
    db_path: Path | None = None,
    max_workers: int | None = None,
    reporter: ProgressReporter | None = None,
) -> IndexResult:
    """Index a repository: parse all Python files and write a knowledge graph.

    Args:
        repo_path: Root directory of the repository to index.
        db_path: Where to create/open the LadybugDB database. Defaults to
            ``repo_path/.compass/graph.ladybug``.
        max_workers: ProcessPoolExecutor pool size. Defaults to ``os.cpu_count()``.
        reporter: Optional progress reporter. Receives updates for
            ``"parse"``, ``"resolve"``, ``"write_nodes"``, and ``"write_edges"`` phases.

    Returns:
        IndexResult: Summary of counts and elapsed time.
    """
    repo_path = repo_path.resolve()
    if db_path is None:
        db_path = repo_path / ".compass" / "graph.ladybug"

    db_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()

    # --- Phase 1: parallel parse ---
    files = list(walk_python_files(repo_path))
    logger.info("Phase 1: parsing %d files with max_workers=%s", len(files), max_workers)
    parsed_files, _ = _run_phase1(files, repo_path, max_workers, reporter=reporter)
    logger.info("Phase 1 complete: %d files parsed successfully", len(parsed_files))

    # --- Phase 2: resolve ---
    graph = resolve(parsed_files, reporter=reporter)

    # --- Phase 3: write graph ---
    with GraphDB(db_path) as db:
        create_schema(db)
        write(db, graph, reporter=reporter)

    elapsed = time.monotonic() - start

    # --- Metadata ---
    commit = _get_git_commit(repo_path)
    _save_metadata(repo_path, commit)

    class_count = sum(len(pf.classes) for pf in parsed_files)
    function_count = sum(
        len(pf.functions) + sum(len(c.methods) for c in pf.classes) for pf in parsed_files
    )

    return IndexResult(
        file_count=len(parsed_files),
        class_count=class_count,
        function_count=function_count,
        elapsed_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# Public phase helpers (used by CLI for granular display)
# ---------------------------------------------------------------------------


def parse_files(
    files: list[Path],
    repo_root: Path,
    max_workers: int | None = None,
    reporter: ProgressReporter | None = None,
) -> tuple[list[ParsedFile], list[Path]]:
    """Parse Python files in parallel using tree-sitter.

    Args:
        files: Absolute paths to the ``.py`` files to parse.
        repo_root: Repository root for module-name derivation.
        max_workers: Process pool size. Defaults to ``os.cpu_count()``.
        reporter: Optional progress reporter. Receives ``"parse"`` updates.

    Returns:
        Tuple of (successfully parsed files, paths that failed to parse).
    """
    return _run_phase1(files, repo_root, max_workers, reporter=reporter)


def save_metadata(repo_path: Path) -> None:
    """Write ``.compass/metadata.json`` with the current HEAD commit hash."""
    commit = _get_git_commit(repo_path)
    _save_metadata(repo_path, commit)


# ---------------------------------------------------------------------------
# Phase 1 — parallel parse (internal)
# ---------------------------------------------------------------------------


def _parse_worker(args: tuple[str, str]) -> ParsedFile | None:
    """Parse one file in a subprocess worker; return None on failure.

    Must be a module-level function so ProcessPoolExecutor can pickle it.

    Args:
        args: Tuple of (absolute file path string, repo root path string).

    Returns:
        ParsedFile | None: The parsed file object, or None if parsing failed.
    """
    path_str, root_str = args
    path = Path(path_str)
    root = Path(root_str)
    try:
        return extract_file(path, root=root)
    except Exception:
        import traceback

        # Use print — worker processes don't share log handlers with the main process
        print(f"[compass] Failed to parse {path}: {traceback.format_exc()}")
        return None


def _run_phase1(
    files: list[Path],
    repo_root: Path,
    max_workers: int | None,
    reporter: ProgressReporter | None = None,
) -> tuple[list[ParsedFile], list[Path]]:
    """Parse files in parallel using ProcessPoolExecutor.

    Args:
        files: Absolute paths to all .py files to parse.
        repo_root: Repository root passed to each worker for module name derivation.
        max_workers: Pool size. Defaults to ``os.cpu_count()``.
        reporter: Optional progress reporter. Receives ``"parse"`` updates.

    Returns:
        Tuple of (successfully parsed files, paths that failed to parse).
    """
    if not files:
        return [], []

    total = len(files)
    # CPU-bound work — use process count, not thread count
    workers = max_workers or os.cpu_count() or 1
    args = [(str(f), str(repo_root)) for f in files]

    parsed: list[ParsedFile] = []
    failed: list[Path] = []
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_path = {executor.submit(_parse_worker, arg): arg[0] for arg in args}
        for future in as_completed(future_to_path):
            path_str = future_to_path[future]
            done += 1
            try:
                result = future.result()
                if result is not None:
                    parsed.append(result)
                else:
                    failed.append(Path(path_str))
            except Exception:
                logger.exception("Worker raised exception for %s", path_str)
                failed.append(Path(path_str))
            if reporter:
                reporter.update("parse", done, total)
    return parsed, failed


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def _get_git_commit(repo_path: Path) -> str:
    """Return the HEAD commit hash, or 'unknown' on any failure.

    Args:
        repo_path: Root directory of the repository to check.

    Returns:
        str: Git commit hash or 'unknown'.
    """
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


def _save_metadata(repo_path: Path, commit: str) -> None:
    """Write .compass/metadata.json with indexed_commit and indexed_at.

    Args:
        repo_path: Repository root — metadata is written under ``repo_path/.compass/``.
        commit: Git commit hash to record, or 'unknown' if unavailable.
    """
    meta_dir = repo_path / ".compass"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "indexed_commit": commit,
        "indexed_at": int(time.time()),
    }
    (meta_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.debug("Metadata written: %s", meta)
