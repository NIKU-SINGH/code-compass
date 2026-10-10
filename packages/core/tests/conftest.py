import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

import compass_core.languages.python  # noqa: F401
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.phases.pipeline import Pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


@pytest.fixture(scope="session")
def fixture_index(tmp_path_factory: pytest.TempPathFactory) -> IndexLocation:
    repo = tmp_path_factory.mktemp("sample_repo")
    shutil.copytree(FIXTURE, repo, dirs_exist_ok=True)
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    return require_index(repo)


@pytest.fixture
def fixture_db(fixture_index: IndexLocation) -> Iterator[GraphDB]:
    with GraphDB(fixture_index.db_path, read_only=True) as db:
        yield db
