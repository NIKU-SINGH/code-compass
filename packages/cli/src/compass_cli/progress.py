"""Rich-based ProgressReporter for the CLI indexing pipeline.

``RichProgressReporter`` is a single context manager that owns one Rich
``Progress`` instance covering all four pipeline phases. Tasks are created
upfront but kept hidden; each task becomes visible the first time its phase
is reported, so the display grows naturally as the pipeline advances.

Adding a new phase
------------------
1. Add a ``(Phase, label)`` entry to ``_TASKS`` below.
2. That is all — no other changes needed in this file or in ``main.py``.
"""

from __future__ import annotations

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn

from compass_core.progress import Phase

_GOLD = "color(214)"

# Ordered list of (phase_key, display_label). The order determines vertical
# position in the terminal — earlier entries appear above later ones.
_TASKS: list[tuple[Phase, str]] = [
    ("parse", "Parsing files      "),
    ("resolve", "Resolving symbols  "),
    ("write_nodes", "Inserting nodes    "),
    ("write_edges", "Inserting edges    "),
]


class RichProgressReporter:
    """Single Rich Progress instance covering all pipeline phases.

    Usage::

        with RichProgressReporter(console=display.console) as reporter:
            parsed, skipped = parse_files(..., reporter=reporter)
            graph = resolve(parsed, reporter=reporter)
            result = write(db, graph, reporter=reporter)
    """

    def __init__(self, console: Console | None = None) -> None:
        self._progress = Progress(
            TextColumn("  {task.description}"),
            BarColumn(bar_width=36, complete_style=_GOLD, finished_style="green"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )
        self._task_ids: dict[str, int] = {}
        for phase, label in _TASKS:
            tid = self._progress.add_task(label, total=None, visible=False, start=False)
            self._task_ids[phase] = tid

    def __enter__(self) -> RichProgressReporter:
        self._progress.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._progress.stop()

    def update(self, phase: Phase, current: int, total: int) -> None:
        """Advance the progress bar for ``phase``.

        The task for ``phase`` is made visible and started on its first call.

        Args:
            phase: The pipeline phase being reported.
            current: Number of items completed so far.
            total: Total number of items for this phase.
        """
        tid = self._task_ids[phase]
        task = self._progress.tasks[tid]
        if not task.visible:
            self._progress.update(tid, visible=True, total=total)
            self._progress.start_task(tid)
        self._progress.update(tid, completed=current, total=total)
