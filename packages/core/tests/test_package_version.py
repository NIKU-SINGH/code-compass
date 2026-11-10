"""``installed_version`` reads compass-code's metadata, and never crashes without it."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from compass_core import package_version
from compass_core.package_version import UNKNOWN, installed_version


def test_reads_the_installed_compass_code_version() -> None:
    found = installed_version()
    assert found != UNKNOWN and found[0].isdigit()


def test_missing_metadata_is_unknown_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(package_version, "version", missing)
    assert installed_version() == UNKNOWN
