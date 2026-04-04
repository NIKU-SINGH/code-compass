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
) -> IndexResult:
    """Index a repository: parse all Python files and write a knowledge graph.

    Args:
        repo_path: Root directory of the repository to index.
        db_path: Where to create/open the LadybugDB database. Defaults to
            ``repo_path/.compass/graph.ladybug``.
        max_workers: ProcessPoolExecutor pool size. Defaults to ``os.cpu_count()``.

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
    parsed_files = _run_phase1(files, repo_path, max_workers)
    logger.info("Phase 1 complete: %d files parsed successfully", len(parsed_files))

    # --- Phase 2 & 3: resolve + write graph ---
    with GraphDB(db_path) as db:
        _run_phase2_and_3(db, parsed_files)

    elapsed = time.monotonic() - start

    # --- Metadata ---
    commit = _get_git_commit(repo_path)
    _save_metadata(repo_path, commit)

    class_count = sum(len(pf.classes) for pf in parsed_files)
    function_count = sum(
        len(pf.functions) + sum(len(c.methods) for c in pf.classes)
        for pf in parsed_files
    )

    return IndexResult(
        file_count=len(parsed_files),
        class_count=class_count,
        function_count=function_count,
        elapsed_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# Phase 1 — parallel parse
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
) -> list[ParsedFile]:
    """Parse files in parallel using ProcessPoolExecutor.

    Args:
        files: Absolute paths to all .py files to parse.
        repo_root: Repository root passed to each worker for module name derivation.
        max_workers: Pool size. Defaults to ``os.cpu_count()``.

    Returns:
        list[ParsedFile]: Only successfully parsed files (None results are dropped).
    """
    if not files:
        return []

    # CPU-bound work — use process count, not thread count
    workers = max_workers or os.cpu_count() or 1
    args = [(str(f), str(repo_root)) for f in files]

    parsed: list[ParsedFile] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_path = {executor.submit(_parse_worker, arg): arg[0] for arg in args}
        for future in as_completed(future_to_path):
            path_str = future_to_path[future]
            try:
                result = future.result()
                if result is not None:
                    parsed.append(result)
            except Exception:
                logger.exception("Worker raised exception for %s", path_str)
    return parsed


# ---------------------------------------------------------------------------
# Phase 2 & 3 — resolve + write
# ---------------------------------------------------------------------------


def _run_phase2_and_3(db: GraphDB, parsed_files: list[ParsedFile]) -> None:
    """Resolve all relationships and write the graph to LadybugDB.

    Phase 2 builds the symbol table and resolves every raw call into a typed,
    confidence-scored edge. Phase 3 persists the result as nodes and edges.

    Args:
        db: Open LadybugDB connection.
        parsed_files: All successfully parsed files from phase 1.
    """
    logger.info("Phase 2: resolving %d files", len(parsed_files))
    graph = resolve(parsed_files)

    logger.info("Phase 3: writing graph to DB")
    create_schema(db)
    write(db, graph)
    logger.info("Phase 3 complete")


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
