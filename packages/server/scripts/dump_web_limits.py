"""Write the web app's generated query limits (``apps/web/src/lib/limits.ts``)."""

import sys
from pathlib import Path

from compass_server.web_limits import render_web_limits


def main(argv: list[str]) -> int:
    """Writes the rendered TypeScript module.

    Args:
        argv: Command-line arguments; ``argv[1]`` is the output path.

    Returns:
        Process exit code: 0 on success, 2 on a usage error.
    """
    if len(argv) != 2:
        print("usage: dump_web_limits.py <limits.ts>", file=sys.stderr)
        return 2
    Path(argv[1]).write_text(render_web_limits(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
