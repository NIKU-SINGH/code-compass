from pathlib import Path

import compass_core.languages.python  # noqa: F401
from compass_core.phases.base import FileManifest, FileMetadata, IngestContext
from compass_core.phases.parse import ParsePhase


def test_parses_all_files_in_manifest(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("def f():\n    return 1\n")
    ctx = IngestContext(repo_root=tmp_path)
    ctx.manifest = FileManifest(
        files=[
            FileMetadata(path=good, language="python", content_hash="x"),
        ]
    )

    result = ParsePhase().run(ctx)

    assert result.parsed_files is not None
    assert len(result.parsed_files) == 1
    assert result.parsed_files[0].degraded is False


def test_one_bad_file_does_not_kill_the_batch(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text("def f():\n    return 1\n")
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"\xff\xfe not valid utf8 or python at all $$$ (((")
    ctx = IngestContext(repo_root=tmp_path)
    ctx.manifest = FileManifest(
        files=[
            FileMetadata(path=good, language="python", content_hash="x"),
            FileMetadata(path=bad, language="python", content_hash="y"),
        ]
    )

    result = ParsePhase().run(ctx)

    assert result.parsed_files is not None
    assert len(result.parsed_files) == 2
    by_name = {Path(pf.path).name: pf for pf in result.parsed_files}
    assert by_name["good.py"].degraded is False
    # tree-sitter is error-tolerant and will still produce a (possibly empty)
    # parse for malformed input rather than raising — degraded reflects an
    # extraction-time exception, not "has syntax errors". This test documents
    # that a garbled-but-decodable file still parses; true worker-exception
    # isolation is covered by test_parse_worker_catches_exceptions_and_sets_degraded
    # below.


def test_parse_worker_catches_exceptions_and_sets_degraded(tmp_path: Path):
    from compass_core.phases.parse import _parse_worker

    missing = tmp_path / "does_not_exist.py"
    result = _parse_worker(("python", str(missing), "does_not_exist.py"))

    assert result.degraded is True
    assert result.error is not None
