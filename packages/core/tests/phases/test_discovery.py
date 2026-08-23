from pathlib import Path

import pytest

import compass_core.languages.python  # noqa: F401  (registers the Python plugin)
from compass_core.phases.base import IngestContext
from compass_core.phases.discovery import DiscoveryPhase


def test_discovers_python_files_with_hash_and_language(tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "README.md").write_text("not code\n")
    ctx = IngestContext(repo_root=tmp_path)

    result = DiscoveryPhase().run(ctx)

    assert result.manifest is not None
    paths = {f.path.name for f in result.manifest.files}
    assert paths == {"a.py"}
    entry = result.manifest.files[0]
    assert entry.language == "python"
    assert len(entry.content_hash) == 64  # sha256 hex digest


def test_skips_gitignored_and_vendored_dirs(tmp_path: Path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.py").write_text("x = 1\n")
    (tmp_path / "real.py").write_text("y = 2\n")
    ctx = IngestContext(repo_root=tmp_path)

    result = DiscoveryPhase().run(ctx)

    names = {f.path.name for f in result.manifest.files}
    assert names == {"real.py"}


def test_not_a_directory_raises_discovery_error(tmp_path: Path):
    from compass_core.errors import DiscoveryError

    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x")
    ctx = IngestContext(repo_root=not_a_dir)

    with pytest.raises(DiscoveryError):
        DiscoveryPhase().run(ctx)


def test_run_writes_back_resolved_repo_root(tmp_path: Path):
    # Real repo dir, plus a symlink pointing at it. Passing the symlink path
    # in reproduces macOS-style mount symlinks (/tmp -> /private/tmp) that
    # tmp_path itself doesn't exercise, since tmp_path is already resolved.
    real_root = tmp_path / "actual_repo"
    real_root.mkdir()
    (real_root / "a.py").write_text("x = 1\n")

    symlinked_root = tmp_path / "repo_via_symlink"
    symlinked_root.symlink_to(real_root)

    assert symlinked_root != symlinked_root.resolve()
    ctx = IngestContext(repo_root=symlinked_root)

    result = DiscoveryPhase().run(ctx)

    # The phase must persist the resolved root back onto ctx, not just use
    # it locally, so that downstream phases (e.g. Task 9's
    # path.relative_to(ctx.repo_root)) see paths and repo_root resolved
    # consistently.
    assert result.repo_root == real_root.resolve()
    assert result.repo_root == result.repo_root.resolve()
    for entry in result.manifest.files:
        entry.path.relative_to(result.repo_root)  # must not raise
