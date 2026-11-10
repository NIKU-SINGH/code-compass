# Releasing Code Compass

Code Compass is published to PyPI as four packages that always share one version:

| Package | Contents |
|---|---|
| `compass-code` | the `compass` command (users install this one) |
| `compass-code-core` | the engine: ingest, graph, queries |
| `compass-code-mcp` | the MCP server |
| `compass-code-server` | the HTTP API and the bundled web UI |

`compass-code` pins the other three to exactly its own version, so an install never mixes
versions. Users install with `uv tool install compass-code` or `pipx install compass-code`.

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

1. On a branch from `main`, set the version of all four packages and refresh the lockfile:

   ```bash
   python scripts/release_version.py set 0.2.0
   uv lock
   ```

2. Open a PR titled `Release 0.2.0` and merge it once CI is green. CI already builds the
   packages and smoke-tests them on Linux and macOS with Python 3.11 and 3.13.
3. Tag the merge commit on `main` and push the tag:

   ```bash
   git checkout main && git pull
   git tag v0.2.0
   git push origin v0.2.0
   ```

The tag starts `.github/workflows/release.yml`, which:

1. checks the tag matches every package's version,
2. runs all of CI (lint, types, tests, web build, package build, smoke tests),
3. publishes the built files to PyPI through Trusted Publishing (no API token is stored),
4. creates a GitHub release with generated notes and the built files attached.

If any step fails nothing is published; fix it on `main`, delete the tag
(`git push --delete origin v0.2.0 && git tag -d v0.2.0`) and tag again. A version that
reached PyPI can never be uploaded again; release the fix as the next patch version.

## One-time setup (before the first release)

**PyPI**: sign in at https://pypi.org, then open *Your projects → Publishing → Add a new
pending publisher* and add one entry **for each of the four package names** above, with:

| Field | Value |
|---|---|
| Owner | `NIKU-SINGH` |
| Repository name | `code-compass` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

**GitHub**: in the repository's *Settings → Environments*, create an environment named
`pypi`. Optionally add yourself as a required reviewer, so every publish waits for your
approval.

## Checking a build locally

```bash
make install-web && make web-static     # bundle the web UI into compass_server
uv build --all-packages -o dist
scripts/smoke_test.sh dist 3.11         # install the wheels fresh and run every command
```
