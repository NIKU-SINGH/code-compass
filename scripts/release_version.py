"""Set the version of ``compass-code``, and check it is ready to release.

Code Compass is developed as four workspace packages but published as one, ``compass-code``
(``packages/cli``), whose wheel bundles the other three (``packages/cli/hatch_build.py``).
So ``compass-code`` must list every third-party dependency of the packages it bundles,
with the same version bounds; ``check`` verifies that, and that a release tag matches.

Usage::

    python scripts/release_version.py check                 # dependencies are complete
    python scripts/release_version.py check --tag v0.2.0    # ...and the tag matches
    python scripts/release_version.py set 0.2.0             # then `uv lock` and commit

Exit status is 0 when everything agrees, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "packages" / "cli" / "pyproject.toml"
"""``compass-code``, the only package uploaded to PyPI."""

BUNDLED = ("core", "mcp", "server")
"""Directories under ``packages/`` whose modules the ``compass-code`` wheel bundles."""

TAG_PREFIX = "v"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+((a|b|rc)\d+)?$")
"""``MAJOR.MINOR.PATCH`` with an optional PEP 440 pre-release (``0.2.0rc1``)."""

_VERSION_LINE = re.compile(r'^version = "[^"]*"$', re.MULTILINE)
_NAME = re.compile(r"^[A-Za-z0-9._-]+")


def _project(path: Path) -> dict[str, object]:
    project: dict[str, object] = tomllib.loads(path.read_text())["project"]
    return project


def _requirements(path: Path) -> dict[str, str]:
    """``{normalised name: full requirement}`` for a pyproject's dependencies."""
    found: dict[str, str] = {}
    dependencies = _project(path).get("dependencies", [])
    assert isinstance(dependencies, list)
    for requirement in dependencies:
        match = _NAME.match(requirement)
        assert match, requirement
        found[match.group(0).lower().replace("_", "-")] = requirement.replace(" ", "")
    return found


def _problems(tag: str | None) -> list[str]:
    """Every reason the published package is not ready, given an optional release tag."""
    problems: list[str] = []
    version = str(_project(PUBLISHED)["version"])
    if not VERSION_PATTERN.match(version):
        problems.append(f"version {version!r} is not MAJOR.MINOR.PATCH[(a|b|rc)N]")
    if tag is not None and tag != f"{TAG_PREFIX}{version}":
        problems.append(f"tag {tag} does not match version {version}")

    workspace = {str(_project(ROOT / "packages" / d / "pyproject.toml")["name"]) for d in BUNDLED}
    published = _requirements(PUBLISHED)
    for directory in BUNDLED:
        pyproject = ROOT / "packages" / directory / "pyproject.toml"
        for name, requirement in _requirements(pyproject).items():
            if name in workspace:
                continue
            if name not in published:
                problems.append(
                    f"compass-code is missing {requirement} (from packages/{directory})"
                )
            elif published[name] != requirement:
                problems.append(
                    f"compass-code has {published[name]}, packages/{directory} has {requirement}"
                )
    return problems


def check(tag: str | None) -> int:
    """Print every problem; the exit status says whether there was one.

    Args:
        tag: The release tag to compare with, e.g. ``v0.2.0``; ``None`` skips it.

    Returns:
        0 when ready, else 1.

    Example:
        ``check("v0.1.0")`` returns 0 while ``compass-code`` is at ``0.1.0`` and lists every
        bundled package's dependencies.
    """
    problems = _problems(tag)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if not problems:
        print("ready" + (f" for {tag}" if tag else ""))
    return 1 if problems else 0


def set_version(new: str) -> int:
    """Write ``new`` as the version of ``compass-code``.

    Args:
        new: The version, e.g. ``0.2.0``.

    Returns:
        0 on success, 1 if ``new`` is not a valid version.

    Example:
        ``set_version("0.2.0")`` turns ``version = "0.1.0"`` into ``version = "0.2.0"`` in
        ``packages/cli/pyproject.toml``.
    """
    if not VERSION_PATTERN.match(new):
        print(f"error: {new!r} is not MAJOR.MINOR.PATCH[(a|b|rc)N]", file=sys.stderr)
        return 1
    PUBLISHED.write_text(_VERSION_LINE.sub(f'version = "{new}"', PUBLISHED.read_text(), count=1))
    print(f"set compass-code to {new}; now run `uv lock` and commit")
    return check(None)


def main() -> int:
    """Parse the command line and run ``check`` or ``set``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser("check", help="verify dependencies and the tag")
    check_parser.add_argument("--tag", help="release tag to compare with, e.g. v0.2.0")
    set_parser = commands.add_parser("set", help="set the version of compass-code")
    set_parser.add_argument("version", help="the new version, e.g. 0.2.0")
    args = parser.parse_args()
    if args.command == "check":
        return check(args.tag)
    return set_version(args.version)


if __name__ == "__main__":
    sys.exit(main())
