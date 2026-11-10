"""Bundle the engine, the MCP server and the HTTP server into the ``compass-code`` wheel.

Code Compass is developed as four workspace packages but published as one, so users and
PyPI deal with a single name. This build hook copies the other three packages' modules
into the release wheel. Editable installs (``uv sync``) are left alone: there each package
is installed from its own folder, so edits take effect without a rebuild.

Build the release wheel from the repository with ``uv build --wheel packages/cli``; an
sdist cannot carry the sibling folders, so none is published.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

BUNDLED = {
    "core/src/compass_core": "compass_core",
    "mcp/src/compass_mcp": "compass_mcp",
    "server/src/compass_server": "compass_server",
}
"""Source folder under ``packages/`` -> module path inside the wheel. The server folder
includes ``static/``, the web UI that ``make web-static`` exports."""

_RELEASE_WHEEL = "standard"


class BundleWorkspacePackages(BuildHookInterface):
    """Copy the sibling workspace packages into a standard (non-editable) wheel."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Add each bundled package to the wheel's force-included files.

        Args:
            version: ``"standard"`` for a release wheel, ``"editable"`` for ``uv sync``.
            build_data: Hatchling's build settings for this wheel.

        Raises:
            FileNotFoundError: If a sibling package is missing, e.g. when building from an
                sdist instead of the repository.
        """
        if version != _RELEASE_WHEEL:
            return
        packages = Path(self.root).parent
        for source, target in BUNDLED.items():
            path = packages / source
            if not path.is_dir():
                raise FileNotFoundError(
                    f"{path} not found; build the wheel from the repository with "
                    "`uv build --wheel packages/cli`"
                )
            build_data["force_include"][str(path)] = target
