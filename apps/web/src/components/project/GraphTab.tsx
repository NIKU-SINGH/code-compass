"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { useGraphData } from "./graph/useGraphData";
import { useExpandableGraph, VisibleNode } from "./graph/useExpandableGraph";
import type { GraphCanvasHandle } from "./graph/GraphCanvas3D";
import { GraphLegend } from "./graph/GraphLegend";
import { Starfield } from "./graph/Starfield";
import { DetailsPanel } from "./graph/DetailsPanel";
import { Input } from "@/components/ui/input";

// 3d-force-graph touches `window` at import time, so it must never be
// pulled into the server bundle.
const GraphCanvas3D = dynamic(
  () => import("./graph/GraphCanvas3D").then((m) => m.GraphCanvas3D),
  { ssr: false }
);

export function GraphTab() {
  const { data, loading, error } = useGraphData();
  const {
    visibleNodes,
    visibleEdges,
    typeVisibility,
    typeCounts,
    toggleType,
    edgeTypeVisibility,
    edgeTypeCounts,
    toggleEdgeType,
    expand,
    revealPathTo,
  } = useExpandableGraph(data);

  const [showLabels, setShowLabels] = useState(true);
  const [search, setSearch] = useState("");
  const [popover, setPopover] = useState<{
    node: VisibleNode;
    x: number;
    y: number;
  } | null>(null);

  const canvasRef = useRef<GraphCanvasHandle>(null);

  // Search reveals the ancestor chain of any matching node so it's visible
  // even if its parents haven't been expanded yet.
  useEffect(() => {
    if (!data || search.trim() === "") return;
    const term = search.toLowerCase();
    data.nodes
      .filter((n) => n.label.toLowerCase().includes(term))
      .forEach((n) => revealPathTo(n.id));
    // revealPathTo is stable across a given `data`, safe to omit from deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, data]);

  const handleNodeClick = useCallback((node: VisibleNode, x: number, y: number) => {
    setPopover({ node, x, y });
  }, []);

  const connectionCount = popover
    ? (data?.edges.filter((e) => e.source === popover.node.id || e.target === popover.node.id)
        .length ?? 0)
    : 0;

  const handleNodeDblClick = useCallback(
    (node: VisibleNode) => {
      expand(node.id);
      setPopover(null);
    },
    [expand]
  );

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="flex-1 relative overflow-hidden">
        <Starfield />

        {/* Top bar: search */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="h-8 text-xs w-56"
          />
        </div>

        <GraphCanvas3D
          ref={canvasRef}
          nodes={visibleNodes}
          edges={visibleEdges}
          showLabels={showLabels}
          onNodeClick={handleNodeClick}
          onNodeDblClick={handleNodeDblClick}
          onBackgroundClick={() => setPopover(null)}
        />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
            Loading graph…
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center px-6">
            <p className="text-sm font-medium text-foreground">No graph data</p>
            <p className="text-xs text-muted-foreground">
              Run{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                compass ingest ./repo
              </code>{" "}
              first.
            </p>
          </div>
        )}

        <GraphLegend
          typeVisibility={typeVisibility}
          typeCounts={typeCounts}
          onToggleType={toggleType}
          edgeTypeVisibility={edgeTypeVisibility}
          edgeTypeCounts={edgeTypeCounts}
          onToggleEdgeType={toggleEdgeType}
          showLabels={showLabels}
          onToggleLabels={() => setShowLabels((v) => !v)}
          onZoomIn={() => canvasRef.current?.zoomIn()}
          onZoomOut={() => canvasRef.current?.zoomOut()}
        />

        <p className="absolute bottom-4 right-4 text-[11px] text-muted-foreground/70 z-10">
          Click to select. Double-click to expand.
        </p>

        {popover && (
          <>
            <div
              className="fixed z-20 bg-card border border-border rounded-lg shadow-lg p-3 text-xs pointer-events-none"
              style={{ left: popover.x + 12, top: popover.y - 8 }}
            >
              <p className="font-semibold text-foreground mb-1">{popover.node.label}</p>
              <p className="text-muted-foreground">{popover.node.type}</p>
              <p className="text-muted-foreground mt-0.5">
                {connectionCount} connection{connectionCount === 1 ? "" : "s"}
              </p>
              {popover.node.hasChildren && (
                <p className="text-muted-foreground/70 mt-1">Double-click to explore connections</p>
              )}
            </div>

            <DetailsPanel
              node={popover.node}
              connectionCount={connectionCount}
              onClose={() => setPopover(null)}
            />
          </>
        )}
      </div>
    </div>
  );
}
