"""Index status for query results: metadata plus a count of stale files."""

from __future__ import annotations

from compass_core.contract.models import IndexStatus
from compass_core.contract.types import RepoPath
from compass_core.graph.db import GraphDB
from compass_core.index.freshness import count_stale
from compass_core.index.locate import IndexLocation
from compass_core.index.metadata import load_metadata
from compass_core.query.cypher import Query
from compass_core.query.rows import text_value

_FILE_PATHS: Query[RepoPath] = Query(
    "MATCH (f:File) RETURN f.path", lambda row: RepoPath(text_value(row[0], "path"))
)


def index_status(location: IndexLocation, db: GraphDB) -> IndexStatus:
    """Describe the index and count its stale files.

    The indexed paths come from the graph; the stale check itself is
    ``index.freshness.count_stale`` (missing, or modified after the ingest).

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
    paths = _FILE_PATHS.run(db)
    return IndexStatus(
        repo_root=repo_root,
        indexed_at=meta.indexed_at,
        indexed_commit=meta.indexed_commit,
        schema_version=meta.schema_version,
        stale_file_count=count_stale(repo_root, paths, int(meta.indexed_at.timestamp())),
        new_file_count=None,
    )
