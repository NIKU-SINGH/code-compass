"use client";

import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { useGraphData, type NodeType } from "./useGraphData";
import { useExpandableGraph, VisibleNode } from "./useExpandableGraph";
import type { GraphCanvasHandle } from "./GraphCanvas3D";
import { GraphLegend } from "./GraphLegend";
import { DetailsPanel } from "./DetailsPanel";
import { Info } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { useWorkspaceView } from "@/components/shell/useWorkspaceView";
import { findFocusedNode } from "./focusMatch";
import { useNodeDetail } from "./useNodeDetail";
import type { SymbolRef } from "@/lib/api";

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
    typeTotals,
    toggleType,
    edgeTypeVisibility,
    edgeTypeCounts,
    edgeTypeTotals,
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
  const focusHidden = Boolean(focusedNode) && !typeVisibility[focusedNode!.type as NodeType];

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

  // Escape clears the selection, unless the user is typing in the search box.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if ((e.target as HTMLElement | null)?.tagName === "INPUT") return;
      setSelection(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleNodeClick = useCallback((node: VisibleNode, x: number, y: number) => {
    setSelection({ id: node.id, x, y });
  }, []);

  const { detail, loading: detailLoading, error: detailError, retry } = useNodeDetail(
    selectedNode?.publicId ?? null
  );

  const nodeByPublicId = useMemo(
    () => new Map((data?.nodes ?? []).map((n) => [n.public_id, n])),
    [data]
  );
  const canSelectRelated = useCallback(
    (symbol: SymbolRef) => nodeByPublicId.has(symbol.id),
    [nodeByPublicId]
  );
  // Related items may be collapsed away in the graph; reveal their path before selecting.
  const selectRelated = useCallback(
    (symbol: SymbolRef) => {
      const target = nodeByPublicId.get(symbol.id);
      if (!target) return;
      revealPathTo(target.id);
      setSelection({ id: target.id });
    },
    [nodeByPublicId, revealPathTo]
  );

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
        {/* Top bar: search */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="h-8 text-xs w-56 bg-card/80 backdrop-blur-md"
          />
          {focusHidden && (
            <Alert role="status" className="py-2 w-auto">
              <Info className="size-4" aria-hidden />
              <AlertDescription>Hidden by the current filters</AlertDescription>
            </Alert>
          )}
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
          totalNodeCount={Object.values(typeTotals).reduce((sum, n) => sum + n, 0)}
          showLabels={showLabels}
          onNodeClick={handleNodeClick}
          onNodeDblClick={handleNodeDblClick}
          onBackgroundClick={() => setSelection(null)}
          focusId={focusedNode?.id ?? null}
          selectedId={selectedNode?.id ?? null}
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
          typeTotals={typeTotals}
          onToggleType={toggleType}
          edgeTypeVisibility={edgeTypeVisibility}
          edgeTypeCounts={edgeTypeCounts}
          edgeTypeTotals={edgeTypeTotals}
          onToggleEdgeType={toggleEdgeType}
          showLabels={showLabels}
          onToggleLabels={() => setShowLabels((v) => !v)}
          onZoomIn={() => canvasRef.current?.zoomIn()}
          onZoomOut={() => canvasRef.current?.zoomOut()}
        />

        <p className="absolute bottom-4 right-4 text-[11px] text-muted-foreground/70 z-10">
          Click to select. Double-click to expand.
        </p>

      </div>

      {selectedNode && (
        <DetailsPanel
          node={selectedNode}
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onRetry={retry}
          onClose={() => setSelection(null)}
          onShowImpact={(node) => setView("impact", node.publicId)}
          onExpand={(node) => expand(node.id)}
          canSelect={canSelectRelated}
          onSelectRelated={selectRelated}
        />
      )}
    </div>
  );
}
