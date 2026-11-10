# Releasing Code Compass

Code Compass is developed as four workspace packages (`packages/core`, `mcp`, `server`
and `cli`) but published to PyPI as **one** package, **`compass-code`**. Its wheel is built
from `packages/cli` and bundles the other three (`packages/cli/hatch_build.py`), including
the web UI that `make web-static` exports into `compass_server/static`. Users install it
with `uv tool install compass-code` or `pipx install compass-code`.

Because the wheel bundles the other packages, `packages/cli/pyproject.toml` lists their
third-party dependencies too. When you add or change a dependency in `core`, `mcp` or
`server`, copy it there; `python scripts/release_version.py check` (run by CI) fails until
you do. Only the wheel is published; an sdist cannot carry the sibling folders.

## Versioning

[Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`, tagged `vMAJOR.MINOR.PATCH`.

- While the version is `0.x`, a **minor** bump (`0.2.0` → `0.3.0`) may break the CLI flags,
  MCP tool names or JSON shapes; a **patch** bump (`0.2.0` → `0.2.1`) is fixes only.
- `1.0.0` is the promise that those stay stable until `2.0.0`.
- Pre-releases are `0.2.0rc1` (tag `v0.2.0rc1`); PyPI and GitHub mark them as pre-releases,
  and `uv tool install compass-code` skips them unless asked.
- The index format has its own number (`SCHEMA_VERSION` in
  `compass_core/index/metadata.py`). When a release bumps it, say so in the release notes:
  users must re-run `compass ingest`.

## Cutting a release

1. On a branch from `main`, set the version of `compass-code` and refresh the lockfile:

   ```bash
   python scripts/release_version.py set 0.2.0
   uv lock
   ```

2. Open a PR titled `Release 0.2.0` and merge it once CI is green. CI already builds the
   wheel and smoke-tests it on Linux and macOS with Python 3.11 and 3.13.
3. Tag the merge commit on `main` and push the tag:

   ```bash
   git checkout main && git pull
   git tag v0.2.0
   git push origin v0.2.0
   ```

The tag starts `.github/workflows/release.yml`, which:

1. checks the tag matches the version of `compass-code`,
2. runs all of CI (lint, types, tests, web build, wheel build, smoke tests on Linux; the
   macOS smoke tests run on the release PR instead, as macOS runners can queue for a long
   time),
3. publishes the wheel to PyPI through Trusted Publishing (no API token is stored),
4. creates a GitHub release with generated notes and the wheel attached.

If any step fails nothing is published. Do not re-run the old run; fix it on `main`, delete the tag
(`git push --delete origin v0.2.0 && git tag -d v0.2.0`) and tag again. A version that
reached PyPI can never be uploaded again; release the fix as the next patch version.

## One-time setup (before the first release)

**PyPI**: sign in at https://pypi.org, open https://pypi.org/manage/account/publishing/
and add one pending publisher (GitHub):

| Field | Value |
|---|---|
| PyPI project name | `compass-code` |
| Owner | `NIKU-SINGH` |
| Repository name | `code-compass` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

A pending publisher does not reserve the name; the first upload does. Release soon after
adding it.

**GitHub**: in the repository's *Settings → Environments*, create an environment named
`pypi`. Optionally add yourself as a required reviewer, so every publish waits for your
approval.

## Checking a build locally

```bash
make install-web && make web-static     # bundle the web UI into compass_server
uv build --wheel packages/cli -o dist   # the one wheel, with every package inside
scripts/smoke_test.sh dist 3.11         # install it fresh and run every command
```
