"""Phase 1: FileManifest -> list[ParsedFile]. tree-sitter parse per file,
dispatched via the language registry, run in ProcessPoolExecutor. Per-file
errors isolate (degraded flag on ParsedFile), never kill the pool — this is
the single most important error-isolation point in the pipeline."""

from __future__ import annotations

import os
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import cache
from pathlib import Path

from compass_core.ir.models import ParsedFile
from compass_core.languages import registry
from compass_core.languages.base import LanguageExtractor
from compass_core.phases.base import IngestContext
from compass_core.shared_types import Language


@cache
def _get_extractor(language_id: Language) -> LanguageExtractor:
    return registry.get_extractor_for_language(language_id)


def _parse_one(language_id: Language, abs_path: str, rel_path: str) -> ParsedFile:
    """rel_path is abs_path made relative to ctx.repo_root by the caller.
    Extractors receive the relative path (per the languages/python module-name
    contract established in Task 5: file_path is repo-relative, not absolute,
    so module-name derivation can build a dotted name without needing root
    itself) — abs_path is only used here, to actually read the file's bytes."""
    extractor = _get_extractor(language_id)
    with open(abs_path, "rb") as f:
        source = f.read()
    return extractor.parse(source, Path(rel_path))


def _parse_worker(args: tuple[Language, str, str]) -> ParsedFile:
    language_id, abs_path, rel_path = args
    try:
        return _parse_one(language_id, abs_path, rel_path)
    except Exception as exc:  # noqa: BLE001 — per-file isolation boundary, see module docstring
        traceback.print_exc()
        return ParsedFile(
            path=rel_path,
            language=language_id,
            module_name="",
            content_hash="",
            definitions=[],
            imports=[],
            call_sites=[],
            degraded=True,
            error=str(exc),
        )


class ParsePhase:
    name = "parse"

    def __init__(self, max_workers: int | None = None) -> None:
        self._max_workers = max_workers

    def run(self, ctx: IngestContext) -> IngestContext:
        assert ctx.manifest is not None, "ParsePhase requires DiscoveryPhase to run first"
        tasks = [
            (f.language, str(f.path), str(f.path.relative_to(ctx.repo_root)))
            for f in ctx.manifest.files
        ]
        workers = self._max_workers or os.cpu_count() or 1

        parsed: list[ParsedFile] = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_parse_worker, task): task for task in tasks}
            for done, future in enumerate(as_completed(futures), start=1):
                parsed.append(future.result())
                if ctx.reporter is not None:
                    ctx.reporter.update("parse", done, len(tasks))

        ctx.parsed_files = parsed
        return ctx
