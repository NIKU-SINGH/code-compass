"use client";

import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { useGraphData } from "./useGraphData";
import { useExpandableGraph, VisibleNode } from "./useExpandableGraph";
import type { GraphCanvasHandle } from "./GraphCanvas3D";
import { GraphLegend } from "./GraphLegend";
import { Starfield } from "./Starfield";
import { DetailsPanel } from "./DetailsPanel";
import { Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { useWorkspaceView } from "@/components/shell/useWorkspaceView";
import { findFocusedNode } from "./focusMatch";

// 3d-force-graph touches `window` at import time, so it must never be
// pulled into the server bundle.
const GraphCanvas3D = dynamic(
  () => import("./GraphCanvas3D").then((m) => m.GraphCanvas3D),
  { ssr: false }
);

export function ExplorerPanel() {
  const { focus, setView } = useWorkspaceView();
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
  // `x`/`y` are absent when the selection came from the URL rather than a click,
  // in which case there is no pointer position to anchor the tooltip to.
  const [selection, setSelection] = useState<{ id: string; x?: number; y?: number } | null>(null);
  const popover = selection
    ? { node: visibleNodes.find((n) => n.id === selection.id), x: selection.x, y: selection.y }
    : null;
  const selectedNode = popover?.node ?? null;

  const focusedNode = useMemo(() => findFocusedNode(data?.nodes ?? [], focus), [data, focus]);
  const focusMissing = Boolean(focus?.trim()) && Boolean(data) && !focusedNode;

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

  // Selecting the node from the URL: make sure it is revealed, then open its panel.
  useEffect(() => {
    if (!focusedNode) return;
    revealPathTo(focusedNode.id);
    setSelection({ id: focusedNode.id });
    // revealPathTo is stable across a given `data`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedNode]);

  const handleNodeClick = useCallback((node: VisibleNode, x: number, y: number) => {
    setSelection({ id: node.id, x, y });
  }, []);

  const connectionCount = selectedNode
    ? (data?.edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
        .length ?? 0)
    : 0;

  const handleNodeDblClick = useCallback(
    (node: VisibleNode) => {
      expand(node.id);
      setSelection(null);
    },
    [expand]
  );

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="flex-1 relative overflow-hidden">
        <Starfield />

        {/* Top bar: search */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="h-8 text-xs w-56 bg-card/80 backdrop-blur-md"
          />
          {focusMissing && (
            <Alert role="status" className="py-2 w-auto">
              <Info className="size-4" aria-hidden />
              <AlertDescription>Node not in the current graph view</AlertDescription>
            </Alert>
          )}
        </div>

        <GraphCanvas3D
          ref={canvasRef}
          nodes={visibleNodes}
          edges={visibleEdges}
          showLabels={showLabels}
          onNodeClick={handleNodeClick}
          onNodeDblClick={handleNodeDblClick}
          onBackgroundClick={() => setSelection(null)}
          focusId={focusedNode?.id ?? null}
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
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">
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

        {selectedNode && (
          <>
            {popover?.x !== undefined && popover.y !== undefined && (
              <div
                className="fixed z-20 bg-card border border-border rounded-lg shadow-lg p-3 text-xs pointer-events-none"
                style={{ left: popover.x + 12, top: popover.y - 8 }}
              >
                <p className="font-semibold text-foreground mb-1">{selectedNode.label}</p>
                <p className="text-muted-foreground">{selectedNode.type}</p>
                <p className="text-muted-foreground mt-0.5">
                  {connectionCount} connection{connectionCount === 1 ? "" : "s"}
                </p>
                {selectedNode.hasChildren && (
                  <p className="text-muted-foreground/70 mt-1">Double-click to explore connections</p>
                )}
              </div>
            )}

            <DetailsPanel
              node={selectedNode}
              connectionCount={connectionCount}
              onClose={() => setSelection(null)}
              onShowImpact={(node) => setView("impact", node.publicId)}
            />
          </>
        )}
      </div>
    </div>
  );
}
