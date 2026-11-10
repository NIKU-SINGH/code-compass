"""Keep the four published packages on one version, and check a release tag against it.

Code Compass publishes ``compass-code`` (the CLI) and the three packages it depends on.
They are released together with the same version, and each pins the others to exactly
that version, so an install never mixes versions.

Usage::

    python scripts/release_version.py check                 # versions and pins agree
    python scripts/release_version.py check --tag v0.2.0    # ...and match the tag
    python scripts/release_version.py set 0.2.0             # bump all four, then `uv lock`

Exit status is 0 when everything agrees, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRS = ("core", "server", "mcp", "cli")
"""Directories under ``packages/`` that are published, dependencies first."""

TAG_PREFIX = "v"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+((a|b|rc)\d+)?$")
"""``MAJOR.MINOR.PATCH`` with an optional PEP 440 pre-release (``0.2.0rc1``)."""

_VERSION_LINE = re.compile(r'^version = "[^"]*"$', re.MULTILINE)
_INTERNAL_PIN = re.compile(r'"(compass-code(?:-[a-z]+)?)==[^"]*"')


def _pyproject(package: str) -> Path:
    return ROOT / "packages" / package / "pyproject.toml"


def _problems(tag: str | None) -> list[str]:
    """Every disagreement between the versions, the internal pins and the tag."""
    projects = {pkg: tomllib.loads(_pyproject(pkg).read_text())["project"] for pkg in PACKAGE_DIRS}
    versions = {project["name"]: project["version"] for project in projects.values()}
    problems: list[str] = []
    expected = versions[projects["cli"]["name"]]
    if not VERSION_PATTERN.match(expected):
        problems.append(f"version {expected!r} is not MAJOR.MINOR.PATCH[(a|b|rc)N]")
    problems += [
        f"{name} is {found}, expected {expected}"
        for name, found in versions.items()
        if found != expected
    ]
    for project in projects.values():
        for requirement in project.get("dependencies", []):
            name, _, pinned = requirement.partition("==")
            if name in versions and pinned != expected:
                problems.append(f"{project['name']} pins {requirement}, expected =={expected}")
    if tag is not None and tag != f"{TAG_PREFIX}{expected}":
        problems.append(f"tag {tag} does not match version {expected}")
    return problems


def check(tag: str | None) -> int:
    """Print every disagreement; the exit status says whether there was one.

    Args:
        tag: The release tag to compare with, e.g. ``v0.2.0``; ``None`` skips it.

    Returns:
        0 when everything agrees, else 1.

    Example:
        ``check("v0.1.0")`` returns 0 while all four packages are at ``0.1.0``.
    """
    problems = _problems(tag)
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if not problems:
        print("versions agree" + (f" with {tag}" if tag else ""))
    return 1 if problems else 0


def set_version(new: str) -> int:
    """Write ``new`` as the version of all four packages and of their internal pins.

    Args:
        new: The version, e.g. ``0.2.0``.

    Returns:
        0 on success, 1 if ``new`` is not a valid version.

    Example:
        ``set_version("0.2.0")`` turns ``version = "0.1.0"`` and
        ``"compass-code-core==0.1.0"`` into their ``0.2.0`` forms.
    """
    if not VERSION_PATTERN.match(new):
        print(f"error: {new!r} is not MAJOR.MINOR.PATCH[(a|b|rc)N]", file=sys.stderr)
        return 1
    for package in PACKAGE_DIRS:
        path = _pyproject(package)
        text = _VERSION_LINE.sub(f'version = "{new}"', path.read_text(), count=1)
        path.write_text(_INTERNAL_PIN.sub(rf'"\1=={new}"', text))
    print(f"set {new}; now run `uv lock` and commit")
    return check(None)


def main() -> int:
    """Parse the command line and run ``check`` or ``set``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check_parser = commands.add_parser("check", help="verify versions, pins and the tag")
    check_parser.add_argument("--tag", help="release tag to compare with, e.g. v0.2.0")
    set_parser = commands.add_parser("set", help="set the version of all four packages")
    set_parser.add_argument("version", help="the new version, e.g. 0.2.0")
    args = parser.parse_args()
    if args.command == "check":
        return check(args.tag)
    return set_version(args.version)


if __name__ == "__main__":
    sys.exit(main())
