import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from compass_core.errors import ErrorCode, IndexBusyError, QueryTimeoutError
from compass_core.graph.db import GraphDB

_HOLD_WRITER = (
    "import sys, time\n"
    "from compass_core.graph.db import GraphDB\n"
    "db = GraphDB(sys.argv[1])\n"
    "print('held', flush=True)\n"
    "time.sleep(30)\n"
)
_CHILD_READY_TIMEOUT_S = 20


def _first_line(proc: subprocess.Popen[str], timeout: float) -> str:
    """The child's first stdout line, or fail after ``timeout`` seconds instead of hanging."""
    lines: queue.Queue[str] = queue.Queue()
    assert proc.stdout is not None
    stdout = proc.stdout
    threading.Thread(target=lambda: lines.put(stdout.readline()), daemon=True).start()
    try:
        return lines.get(timeout=timeout)
    except queue.Empty:
        pytest.fail(f"child process printed nothing within {timeout} s")


def test_initialization(tmp_path: Path) -> None:
    db = GraphDB(tmp_path / "test.ladybug")
    assert db is not None
    db.close()


def test_read_only_rejects_writes(tmp_path: Path) -> None:
    path = tmp_path / "g.ladybug"
    with GraphDB(path) as db:
        db.execute("CREATE NODE TABLE T(id STRING, PRIMARY KEY(id))")
    with GraphDB(path, read_only=True) as db, pytest.raises(Exception):  # noqa: B017
        db.execute("CREATE (:T {id: 'x'})")


def test_second_process_writer_maps_to_index_busy(tmp_path: Path) -> None:
    # The driver does not lock between handles inside one process, so a real
    # second process must hold the write lock.
    path = tmp_path / "g.ladybug"
    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLD_WRITER, str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert _first_line(proc, _CHILD_READY_TIMEOUT_S).strip() == "held"
        with pytest.raises(IndexBusyError) as exc:
            GraphDB(path, read_only=True)
        assert exc.value.code is ErrorCode.INDEX_BUSY
        assert exc.value.retry_after_s >= 1
        assert exc.value.__cause__ is not None
    finally:
        proc.kill()
        proc.communicate(timeout=10)  # reaps the child and closes its pipes


def test_slow_query_maps_to_query_timeout(tmp_path: Path) -> None:
    path = tmp_path / "g.ladybug"
    with GraphDB(path) as db:
        db.execute("CREATE NODE TABLE T(id INT64, PRIMARY KEY(id))")
        db.execute("UNWIND range(1, 3000) AS i CREATE (:T {id: i})")
    # Reopen with a tiny timeout so setup statements are not interrupted.
    with GraphDB(path, timeout_ms=1) as db, pytest.raises(QueryTimeoutError) as exc:
        db.execute("MATCH (a:T), (b:T), (c:T) WHERE a.id + b.id + c.id = 7 RETURN count(*)")
    assert exc.value.code is ErrorCode.QUERY_TIMEOUT
    assert exc.value.timeout_ms == 1
    assert exc.value.__cause__ is not None
