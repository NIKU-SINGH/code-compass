"""The web app's ``limits.ts`` is generated from the contract and up to date."""

from pathlib import Path

from compass_server.web_limits import WEB_LIMITS_PATH, render_web_limits

REPO_ROOT = Path(__file__).parents[3]


def test_committed_web_limits_match_the_contract() -> None:
    committed = (REPO_ROOT / WEB_LIMITS_PATH).read_text(encoding="utf-8")
    assert committed == render_web_limits(), "run `make gen-api` and commit limits.ts"
