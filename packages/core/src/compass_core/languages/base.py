"""Plugin contracts. Every language extractor/import resolver must satisfy
these Protocols — enforced by mypy --strict in CI (Task 16), not just at
review time."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from compass_core.ir.models import ParsedFile
from compass_core.shared_types import Language


@runtime_checkable
class LanguageExtractor(Protocol):
    language_id: Language
    file_extensions: set[str]

    def parse(self, source: bytes, file_path: Path) -> ParsedFile: ...


@runtime_checkable
class ImportResolver(Protocol):
    language_id: Language

    def resolve(self, files: list[ParsedFile]) -> dict[str, dict[str, str | None]]: ...
