"""Rich Live table reporter for the CLI ingest pipeline.

``IngestReporter`` owns a single Rich ``Live`` table with one row per
pipeline stage (STAGE / RESULT / TIME). A row appears the moment its stage
starts, shows a live current/total counter while running (for stages that
report granular progress — parse, persistence), and freezes to its final
summary text once the stage completes via ``complete()``.

Adding a new phase
-------------------
1. Add a ``(phase_name, stage_label)`` entry to ``_STAGE_LABELS``.
2. If the phase reports granular progress, map its ``ProgressReporter``
   phase name(s) to it in ``_REPORTER_TO_STAGE``.
3. Call ``reporter.complete(phase_name, primary, secondary, warn=...)`` from
   the CLI once that phase finishes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from compass_core.progress import Phase

_GOLD = "color(214)"
_GREEN = "green"
_WARN = "color(208)"
_DIM = "dim"
_BAR_WIDTH = 14
_DOT_THRESHOLD = 0.12

_STAGE_LABELS: dict[str, str] = {
    "discovery": "discover",
    "parse": "parse",
    "symbol_table": "symbols",
    "resolution": "resolve",
    "validation": "validate",
    "persistence": "write",
}
_STAGE_ORDER = list(_STAGE_LABELS)

# ProgressReporter phase names (fine-grained, item-level) mapped onto the
# pipeline stage whose row they should update while it runs.
_REPORTER_TO_STAGE: dict[str, str] = {
    "parse": "parse",
    "write_nodes": "persistence",
    "write_edges": "persistence",
}


@dataclass
class _StageRow:
    status: str = "pending"  # pending | running | done
    primary: str = ""
    secondary: str = ""
    warn: bool = False
    start: float | None = None
    duration: float | None = None
    current: int = 0
    total: int = 0


def fmt_duration(seconds: float) -> str:
    if seconds >= 60:
        minutes, rest = divmod(seconds, 60)
        return f"{int(minutes)}m {rest:.0f}s"
    return f"{seconds:.1f}s"


def _bar(frac: float, *, style: str) -> Text:
    frac = max(0.0, min(1.0, frac))
    if frac < _DOT_THRESHOLD:
        return Text("●", style=_DIM)
    filled = max(1, round(frac * _BAR_WIDTH))
    return Text("━" * filled, style=style)


class IngestReporter:
    """Live Rich table of pipeline stages; also satisfies ``ProgressReporter``."""

    def __init__(self, console: Console | None = None) -> None:
        self._rows: dict[str, _StageRow] = {name: _StageRow() for name in _STAGE_ORDER}
        self._show_total = False
        self._live = Live(self._render(), console=console, refresh_per_second=8, transient=False)

    def __enter__(self) -> IngestReporter:
        self._live.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._live.stop()

    # -- ProgressReporter protocol -----------------------------------------

    def update(self, phase: Phase, current: int, total: int) -> None:
        """Update the live current/total counter for the stage *phase* maps to."""
        stage = _REPORTER_TO_STAGE.get(phase)
        if stage is None:
            return
        row = self._rows[stage]
        if row.status == "pending":
            row.status = "running"
            row.start = time.monotonic()
        row.current, row.total = current, total
        self._refresh()

    # -- CLI-facing API -------------------------------------------------------

    def complete(self, phase: str, primary: str, secondary: str, *, warn: bool = False) -> None:
        """Freeze *phase*'s row with its final summary text and elapsed duration."""
        row = self._rows[phase]
        now = time.monotonic()
        if row.start is None:
            row.start = now
        row.duration = now - row.start
        row.status = "done"
        row.primary = primary
        row.secondary = secondary
        row.warn = warn
        self._refresh()

    def finalize(self) -> None:
        """Show the total row and stop the live display."""
        self._show_total = True
        self._refresh()
        self._live.stop()

    @property
    def total_duration(self) -> float:
        return sum(r.duration or 0.0 for r in self._rows.values())

    # -- rendering --------------------------------------------------------

    def _refresh(self) -> None:
        self._live.update(self._render())

    def _render(self) -> RenderableType:
        table = Table.grid(padding=(0, 3))
        table.add_column(min_width=9)
        table.add_column(min_width=26)
        table.add_column(justify="right", min_width=10)

        table.add_row(
            Text("STAGE", style=_DIM), Text("RESULT", style=_DIM), Text("TIME", style=_DIM)
        )

        max_duration = max((r.duration for r in self._rows.values() if r.duration), default=0.0)
        for name in _STAGE_ORDER:
            row = self._rows[name]
            if row.status == "pending":
                continue
            label = _STAGE_LABELS[name]

            if row.status == "running":
                stage_text = Text(label, style=f"bold {_GOLD}")
                progress_text = Text(
                    f"{row.current:,} / {row.total:,}" if row.total else "working…"
                )
                table.add_row(stage_text, progress_text, Spinner("dots", style=_GOLD))
                continue

            style = _WARN if row.warn else "bold"
            stage_text = Text(label, style=style)
            result: RenderableType = (
                Group(Text(row.primary, style=style), Text(row.secondary, style=_DIM))
                if row.secondary
                else Text(row.primary, style=style)
            )
            frac = ((row.duration or 0.0) / max_duration) if max_duration else 0.0
            bar_style = _WARN if row.warn else (_GREEN if frac >= _DOT_THRESHOLD else _DIM)
            time_cell = Group(
                Text(fmt_duration(row.duration or 0.0), justify="right"),
                _bar(frac, style=bar_style),
            )
            table.add_row(stage_text, result, time_cell)
            table.add_row("", "", "")

        if self._show_total:
            table.add_row("", "", "")
            table.add_row(
                Text("total", style=_DIM),
                Text(""),
                Text(fmt_duration(self.total_duration), style="bold", justify="right"),
            )
        return table
