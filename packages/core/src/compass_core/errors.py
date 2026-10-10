"""Exception hierarchy for compass_core.

Reserved for genuinely unexpected/unrecoverable failures (DB connection
lost, malformed grammar binary, config missing) that propagate up to
phases/pipeline.py and are caught once at the top level. Expected failures
(an unresolved call site, a degraded parse) are modeled as typed result
objects elsewhere, never raised as one of these.
"""

from __future__ import annotations

from pathlib import Path


class CompassError(Exception):
    """Base exception for compass_core. Carries enough context to debug without re-running."""

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        language: str | None = None,
        phase_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.language = language
        self.phase_name = phase_name


class DiscoveryError(CompassError):
    """Phase 0 failure — repo walk or manifest construction failed unrecoverably."""


class ParseError(CompassError):
    """Phase 1 failure. Only raised for unrecoverable extractor setup failures
    (e.g. grammar binary missing) — per-file parse failures are captured as a
    `degraded` flag on ParsedFile, not raised."""


class UnsupportedLanguageError(ParseError):
    """Raised by languages/registry.py when no extractor is registered for a file's language."""


class ResolutionError(CompassError):
    """Phase 3 failure — unrecoverable failure building the symbol table or resolving edges."""


class ValidationError(CompassError):
    """Phase 4 failure — the ingest run failed a regression gate check."""


class PersistenceError(CompassError):
    """Phase 5 failure — DB connection lost or write failed unrecoverably mid-batch."""


class IndexNotFoundError(CompassError):
    """No ``.compass/graph.ladybug`` was found walking up from ``searched_from``."""

    def __init__(self, *, searched_from: Path) -> None:
        super().__init__(f"No Compass index found from {searched_from}. Run `compass ingest`.")
        self.searched_from = searched_from


class IndexIncompatibleError(CompassError):
    """The index or its metadata is unreadable or from an unsupported version."""
