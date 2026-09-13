"""Progress reporting protocol for pipeline phases.

Core modules call ``reporter.update(phase, current, total)`` without any
dependency on display libraries. The CLI layer provides a concrete
``IngestReporter`` implementation (a live Rich table); tests can use a null
or recording stub that satisfies the same protocol.

Adding a new phase
------------------
1. Add its name to the ``Phase`` literal.
2. Call ``reporter.update("<new_phase>", current, total)`` in the relevant
   core module.
3. Wire it up in ``compass_cli.progress.IngestReporter``.

Nothing else needs to change.
"""

from __future__ import annotations

from typing import Literal, Protocol

Phase = Literal[
    "discovery",
    "parse",
    "symbol_table",
    "resolution",
    "validation",
    "resolve",
    "write_nodes",
    "write_edges",
]


class ProgressReporter(Protocol):
    """Minimal interface for reporting progress across pipeline phases."""

    def update(self, phase: Phase, current: int, total: int) -> None:
        """Report progress for a pipeline phase.

        Args:
            phase: The pipeline phase being reported (e.g. ``"parse"``).
            current: Number of items completed so far.
            total: Total number of items for this phase.
        """
        ...
