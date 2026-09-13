"""Phase 5: ResolvedGraph -> LadybugDB. Nodes before edges, per
graph/writer.py's write order (File -> Class -> Function -> ExternalFunction
nodes, then CONTAINS -> IMPORTS -> INHERITS -> CALLS -> CALLS_EXTERN edges).

Deliberately deviates from the uniform Phase Protocol: `run` takes an extra
`db: GraphDB` argument because the DB connection is a context-managed
resource owned by phases/pipeline.py, not something this phase constructs
itself. pipeline.py calls this phase specially, not through the generic
phase loop."""

from __future__ import annotations

from compass_core.errors import PersistenceError
from compass_core.graph.db import GraphDB
from compass_core.graph.writer import write
from compass_core.phases.base import IngestContext


class PersistencePhase:
    name = "persistence"

    def run(self, ctx: IngestContext, db: GraphDB) -> IngestContext:
        assert ctx.resolved_graph is not None
        try:
            ctx.write_result = write(db, ctx.resolved_graph, reporter=ctx.reporter)
        except PersistenceError:
            raise
        except Exception as exc:  # noqa: BLE001 — unrecoverable DB failure boundary
            raise PersistenceError(
                f"failed to persist resolved graph: {exc}",
                phase_name=self.name,
            ) from exc
        return ctx
