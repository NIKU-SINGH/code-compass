"""Index freshness for query results."""

from __future__ import annotations

from pathlib import Path

from compass_core.graph.db import GraphDB, as_rows
from compass_core.index.locate import IndexLocation
from compass_core.index.metadata import load_metadata
from compass_core.query.models import IndexStatus
from compass_core.query.rows import to_repo_path


def _is_stale(path: Path, indexed_at: int) -> bool:
    """Whether ``path`` is missing or was modified after ``indexed_at`` (epoch seconds)."""
    try:
        return int(path.stat().st_mtime) > indexed_at
    except OSError:
        return True


def index_status(location: IndexLocation, db: GraphDB) -> IndexStatus:
    """Describe the index and count its stale files.

    A file is stale when it no longer exists or its mtime is later than the ingest
    time. Metadata stores whole seconds, so mtimes are compared at second resolution
    to keep a just-ingested file from looking stale. Consequently an edit made within
    the same second as the ingest is invisible (a false negative). Every indexed file
    is stat'ed on each call, so callers may want to cache the result.

    Args:
        location: Where the index lives.
        db: Open graph database of that index.

    Returns:
        The status, with ``new_file_count`` left ``None`` (only ``status`` computes it).

    Raises:
        IndexIncompatibleError: The metadata or a stored row is unreadable.

    Example:
        After ``touch app/auth.py`` post-ingest, ``index_status(loc, db).stale_file_count``
        is ``1``.
    """
    meta = load_metadata(location.metadata_path)
    repo_root = location.repo_root.resolve()
    indexed_at = int(meta.indexed_at.timestamp())
    stale = 0
    for row in as_rows(db.execute("MATCH (f:File) RETURN f.path")):
        stored = row[0]
        if not isinstance(stored, str):
            continue
        if _is_stale(repo_root / to_repo_path(stored, repo_root), indexed_at):
            stale += 1
    return IndexStatus(
        repo_root=repo_root,
        indexed_at=meta.indexed_at,
        indexed_commit=meta.indexed_commit,
        schema_version=meta.schema_version,
        stale_file_count=stale,
        new_file_count=None,
    )
