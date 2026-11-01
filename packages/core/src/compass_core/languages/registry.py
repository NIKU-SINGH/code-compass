"""Extension/language-id -> plugin lookup. No phase past Phase 1 may know a
specific language — this module is the only place that maps a file
extension to a concrete LanguageExtractor."""

from __future__ import annotations

from compass_core.errors import UnsupportedLanguageError
from compass_core.languages.base import ImportResolver, LanguageExtractor
from compass_core.shared_types import Language

_extractors_by_extension: dict[str, LanguageExtractor] = {}
_extractors_by_language: dict[Language, LanguageExtractor] = {}
_import_resolvers_by_language: dict[Language, ImportResolver] = {}


def register_extractor(extractor: LanguageExtractor) -> None:
    for ext in extractor.file_extensions:
        _extractors_by_extension[ext] = extractor
    _extractors_by_language[extractor.language_id] = extractor


def register_import_resolver(resolver: ImportResolver) -> None:
    _import_resolvers_by_language[resolver.language_id] = resolver


def get_extractor_for_extension(ext: str) -> LanguageExtractor:
    try:
        return _extractors_by_extension[ext]
    except KeyError:
        raise UnsupportedLanguageError(
            f"no extractor registered for extension {ext!r}", language=ext
        ) from None


def get_extractor_for_language(language_id: Language) -> LanguageExtractor:
    try:
        return _extractors_by_language[language_id]
    except KeyError:
        raise UnsupportedLanguageError(
            f"no extractor registered for language {language_id!r}", language=language_id
        ) from None


def get_import_resolver(language_id: Language) -> ImportResolver:
    try:
        return _import_resolvers_by_language[language_id]
    except KeyError:
        raise UnsupportedLanguageError(
            f"no import resolver registered for language {language_id!r}", language=language_id
        ) from None


def registered_extensions() -> set[str]:
    return set(_extractors_by_extension.keys())


def _snapshot_for_tests() -> tuple[
    dict[str, LanguageExtractor], dict[Language, LanguageExtractor], dict[Language, ImportResolver]
]:
    """Test-only: capture current registry state so it can be restored after a test wipes it."""
    return (
        dict(_extractors_by_extension),
        dict(_extractors_by_language),
        dict(_import_resolvers_by_language),
    )


def _restore_for_tests(
    snapshot: tuple[
        dict[str, LanguageExtractor],
        dict[Language, LanguageExtractor],
        dict[Language, ImportResolver],
    ],
) -> None:
    """Test-only: restore registry state captured by _snapshot_for_tests."""
    by_ext, by_lang, resolvers = snapshot
    _extractors_by_extension.clear()
    _extractors_by_extension.update(by_ext)
    _extractors_by_language.clear()
    _extractors_by_language.update(by_lang)
    _import_resolvers_by_language.clear()
    _import_resolvers_by_language.update(resolvers)


def _reset_for_tests() -> None:
    """Test-only: clear registry state between tests. Not part of the public API."""
    _extractors_by_extension.clear()
    _extractors_by_language.clear()
    _import_resolvers_by_language.clear()
