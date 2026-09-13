from pathlib import Path

import pytest

from compass_core.errors import UnsupportedLanguageError
from compass_core.ir.models import ParsedFile
from compass_core.languages import registry
from compass_core.languages.base import ImportResolver, LanguageExtractor


class _FakeExtractor:
    language_id = "fake"
    file_extensions = {".fk"}

    def parse(self, source: bytes, file_path: Path) -> ParsedFile:
        return ParsedFile(
            path=str(file_path),
            language="fake",
            module_name="fake",
            content_hash="x",
            definitions=[],
            imports=[],
            call_sites=[],
        )


class _FakeImportResolver:
    language_id = "fake"

    def resolve(self, files: list[ParsedFile]) -> dict[str, dict[str, str | None]]:
        return {}


@pytest.fixture(autouse=True)
def _clean_registry():
    snapshot = registry._snapshot_for_tests()
    registry._reset_for_tests()
    yield
    registry._reset_for_tests()
    registry._restore_for_tests(snapshot)


def test_extractor_conforms_to_protocol():
    ext = _FakeExtractor()
    assert isinstance(ext, LanguageExtractor)


def test_register_and_lookup_by_extension():
    registry.register_extractor(_FakeExtractor())
    found = registry.get_extractor_for_extension(".fk")
    assert found.language_id == "fake"


def test_register_and_lookup_by_language_id():
    registry.register_extractor(_FakeExtractor())
    found = registry.get_extractor_for_language("fake")
    assert found.language_id == "fake"


def test_unknown_extension_raises_unsupported_language_error():
    with pytest.raises(UnsupportedLanguageError):
        registry.get_extractor_for_extension(".nope")


def test_import_resolver_registration():
    registry.register_import_resolver(_FakeImportResolver())
    found = registry.get_import_resolver("fake")
    assert isinstance(found, ImportResolver)
