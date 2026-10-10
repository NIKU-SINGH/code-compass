"""Dump the FastAPI OpenAPI schema to a file without running a server."""

import json
import sys
from pathlib import Path

from compass_core.server.main import app


def main(argv: list[str]) -> int:
    """Writes the app's OpenAPI document as indented JSON.

    Args:
        argv: Command-line arguments; ``argv[1]`` is the output path. Parent
            directories are created when missing.

    Returns:
        Process exit code: 0 on success, 2 on a usage error.
    """
    if len(argv) != 2:
        print("usage: dump_openapi.py <output.json>", file=sys.stderr)
        return 2
    out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
