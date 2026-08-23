from pathlib import Path

from compass_core.phases.base import FileManifest, FileMetadata, IngestContext, Phase


def test_ingest_context_starts_mostly_empty():
    ctx = IngestContext(repo_root=Path("/tmp/repo"))
    assert ctx.manifest is None
    assert ctx.parsed_files is None
    assert ctx.resolved_graph is None
    assert ctx.report is None


def test_file_manifest_holds_metadata():
    fm = FileManifest(files=[FileMetadata(path=Path("a.py"), language="python", content_hash="x")])
    assert fm.files[0].language == "python"


def test_a_phase_implementation_satisfies_protocol():
    class NoOpPhase:
        name = "noop"

        def run(self, ctx: IngestContext) -> IngestContext:
            return ctx

    phase = NoOpPhase()
    assert isinstance(phase, Phase)
    ctx = IngestContext(repo_root=Path("/tmp/repo"))
    assert phase.run(ctx) is ctx
