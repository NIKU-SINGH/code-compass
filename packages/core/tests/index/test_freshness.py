import os
from pathlib import Path

from compass_core.index.freshness import count_stale, is_stale


def _file(root: Path, name: str, mtime: int) -> Path:
    path = root / name
    path.write_text("x = 1\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_unchanged_file_is_fresh(tmp_path: Path) -> None:
    assert not is_stale(_file(tmp_path, "a.py", 1_000), indexed_at=1_000)


def test_file_modified_after_ingest_is_stale(tmp_path: Path) -> None:
    assert is_stale(_file(tmp_path, "a.py", 1_001), indexed_at=1_000)


def test_missing_file_is_stale(tmp_path: Path) -> None:
    assert is_stale(tmp_path / "gone.py", indexed_at=1_000)


def test_count_stale_counts_changed_and_missing(tmp_path: Path) -> None:
    _file(tmp_path, "fresh.py", 900)
    _file(tmp_path, "changed.py", 1_100)
    assert count_stale(tmp_path, ["fresh.py", "changed.py", "gone.py"], indexed_at=1_000) == 2
