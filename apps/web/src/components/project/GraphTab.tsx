"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { apiFetch } from "@/lib/api";
import {
  FilterPanel,
  FilterState,
  DEFAULT_FILTER_STATE,
  NodeType,
  EdgeType,
} from "./FilterPanel";

const NODE_COLOR: Record<NodeType, string> = {
  File:        "#60a5fa", // blue  — structural containers
  Class:       "#fb923c", // orange — class definitions
  Function:    "#4ade80", // green  — functions
  Method:      "#c084fc", // violet — methods
  ExternalDep: "#f87171", // red    — external deps
  Field:       "#e879f9", // fuchsia — fields
};

const NODE_SIZE: Record<NodeType, number> = {
  File:        14,
  Class:       10,
  Function:    7,
  Method:      7,
  ExternalDep: 5,
  Field:       5,
};

const EDGE_COLOR: Record<EdgeType, string> = {
  CONTAINS:    "#4ade80",
  IMPORTS:     "#60a5fa",
  INHERITS:    "#fb923c",
  CALLS:       "rgba(255,255,255,0.12)",
  CALLS_EXTERN:"#f87171",
};

interface ApiNode { id: string; label: string; type: string; file_path: string; }
interface ApiEdge { id: string; source: string; target: string; type: string; }
interface GraphData { nodes: ApiNode[]; edges: ApiEdge[]; }

export function GraphTab({ projectId }: { projectId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef     = useRef<Sigma | null>(null);
  const graphRef     = useRef<Graph | null>(null);
  const [filter, setFilter]   = useState<FilterState>(DEFAULT_FILTER_STATE);
  const [search, setSearch]   = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [popover, setPopover] = useState<{
    nodeId: string;
    label: string;
    nodeType: string;
    filePath: string;
    x: number;
    y: number;
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Kill any existing sigma instance and clear stale canvases (React StrictMode runs effects twice)
    sigmaRef.current?.kill();
    sigmaRef.current = null;
    graphRef.current = null;
    containerRef.current.innerHTML = "";

    let sigma: Sigma | null = null;
    let cancelled = false;

    apiFetch<GraphData>("/api/repo/graph")
      .then((data) => {
        if (cancelled || !containerRef.current) return;
        const graph = new Graph({ multi: false, type: "directed" });

        data.nodes.forEach((n) => {
          const nodeType = n.type as NodeType;
          graph.addNode(n.id, {
            label:    n.label,
            nodeType,
            filePath: n.file_path,
            color:    NODE_COLOR[nodeType] ?? "#6b7280",
            size:     NODE_SIZE[nodeType]  ?? 6,
            x:        Math.random(),
            y:        Math.random(),
          });
        });

        data.edges.forEach((e) => {
          try {
            graph.addEdgeWithKey(e.id, e.source, e.target, {
              edgeType: e.type as EdgeType,
              type:     "line",
              color:    EDGE_COLOR[e.type as EdgeType] ?? "rgba(255,255,255,0.20)",
              size:     2,
            });
          } catch {
            // skip duplicate or missing-node edges
          }
        });

        // Solar-system layout: each file is a "sun" with its children orbiting it.
        // Recursive solar layout — no forceAtlas2 so coordinates stay predictable.
        // Each parent is a "sun"; children orbit it at a radius large enough that
        // edges are visible beyond node circles.
        const childrenOf: Record<string, string[]> = {};
        graph.forEachEdge((_e, attrs, src, tgt) => {
          if (attrs.edgeType === "CONTAINS")
            (childrenOf[src] = childrenOf[src] ?? []).push(tgt);
        });

        // Orbit radius in graph units: large enough to peek past node circles.
        // Sigma node sizes (7–14) are in screen px; 1 graph unit ≈ viewport/coordRange px.
        // Using 25+ units ensures edges are always visible.
        const orbitRadius = (childCount: number) =>
          Math.max(25, Math.sqrt(childCount) * 12);

        function placeSubtree(id: string, cx: number, cy: number, scale: number) {
          graph.setNodeAttribute(id, "x", cx);
          graph.setNodeAttribute(id, "y", cy);
          const kids = childrenOf[id] ?? [];
          if (!kids.length) return;
          const r = orbitRadius(kids.length) * scale;
          kids.forEach((kid, i) => {
            const angle = (i / kids.length) * 2 * Math.PI - Math.PI / 2;
            placeSubtree(kid, cx + Math.cos(angle) * r, cy + Math.sin(angle) * r, 0.45);
          });
        }

        // Root nodes = nodes with no incoming CONTAINS edge
        const allChildren = new Set(Object.values(childrenOf).flat());
        const roots = graph.nodes().filter(n => !allChildren.has(n));

        // Phyllotaxis (golden-angle) scatter — looks organic, avoids grids/lines.
        // Each root is placed at angle = i * goldenAngle, radius grows with √i
        // so groups spread outward evenly without clustering.
        const golden = Math.PI * (3 - Math.sqrt(5)); // ≈ 137.5°
        const spacing = 90;
        roots.forEach((root, idx) => {
          const groupR = orbitRadius((childrenOf[root] ?? []).length);
          const r = Math.sqrt(idx + 0.5) * (spacing + groupR * 0.4);
          const angle = idx * golden;
          placeSubtree(root, Math.cos(angle) * r, Math.sin(angle) * r, 1);
        });

        graphRef.current = graph;

        sigma = new Sigma(graph, containerRef.current!, {
          renderEdgeLabels:          false,
          defaultEdgeType:           "line",
          defaultEdgeColor:          "rgba(255,255,255,0.20)",
          defaultNodeColor:          "#60a5fa",
          labelColor:                { color: "rgba(255,255,255,0.85)" },
          labelSize:                 11,
          labelWeight:               "500",
          labelRenderedSizeThreshold: 4,
          stagePadding:              40,
          enableEdgeEvents:          false,
        });

        sigma.on("clickNode", ({ node }) => {
          const attrs = graph.getNodeAttributes(node);
          const rect = containerRef.current!.getBoundingClientRect();
          const vp = sigma!.graphToViewport({ x: attrs.x as number, y: attrs.y as number });
          setPopover({
            nodeId:   node,
            label:    attrs.label as string,
            nodeType: attrs.nodeType as string,
            filePath: attrs.filePath as string,
            x: rect.left + vp.x,
            y: rect.top  + vp.y,
          });
        });

        sigma.on("clickStage", () => setPopover(null));

        sigmaRef.current = sigma;
        // Start zoomed in — ratio < 1 means closer to nodes in sigma's camera model
        sigma.getCamera().setState({ x: 0.5, y: 0.5, angle: 0, ratio: 0.5 });
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setLoading(false);
      });

    return () => {
      cancelled = true;
      sigma?.kill();
      sigmaRef.current = null;
      graphRef.current = null;
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
  }, [projectId]);

  // Apply filter state to graph
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    graph.forEachNode((node, attrs) => {
      const type = attrs.nodeType as NodeType;
      graph.setNodeAttribute(node, "hidden", !filter.nodes[type]);
    });

    graph.forEachEdge((edge, attrs) => {
      const type = attrs.edgeType as EdgeType;
      const srcHidden = graph.getNodeAttribute(graph.source(edge), "hidden") as boolean;
      const tgtHidden = graph.getNodeAttribute(graph.target(edge), "hidden") as boolean;
      graph.setEdgeAttribute(edge, "hidden", !filter.edges[type] || srcHidden || tgtHidden);
    });

    sigmaRef.current?.scheduleRefresh();
  }, [filter]);

  // Apply label visibility
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.forEachNode((node, attrs) => {
      graph.setNodeAttribute(node, "label", filter.showLabels ? (attrs.label as string) : "");
    });
    sigmaRef.current?.scheduleRefresh();
  }, [filter.showLabels]);

  // Search filter
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    if (search === "") {
      graph.forEachNode((node, attrs) => {
        const type = attrs.nodeType as NodeType;
        graph.setNodeAttribute(node, "hidden", !filter.nodes[type]);
      });
    } else {
      const term = search.toLowerCase();
      graph.forEachNode((node, attrs) => {
        const matches = (attrs.label as string).toLowerCase().includes(term);
        graph.setNodeAttribute(node, "hidden", !matches);
      });
    }

    sigmaRef.current?.scheduleRefresh();
  }, [search, filter.nodes]);

  // Layout switching
  const applyLayout = useCallback((layout: FilterState["layout"]) => {
    const graph = graphRef.current;
    if (!graph) return;
    if (layout === "force") {
      forceAtlas2.assign(graph, {
        iterations: 150,
        settings: { gravity: 0.05, scalingRatio: 20, barnesHutOptimize: true, slowDown: 15 },
      });
    } else if (layout === "radial") {
      // Radial: nodes in a circle ordered by type
      const nodes = graph.nodes().sort((a, b) => {
        const order: Record<string, number> = { File: 0, Class: 1, Function: 2, Method: 3, ExternalDep: 4, Field: 5 };
        return (order[graph.getNodeAttribute(a, "nodeType")] ?? 9) - (order[graph.getNodeAttribute(b, "nodeType")] ?? 9);
      });
      nodes.forEach((n, i) => {
        const angle = (i / nodes.length) * 2 * Math.PI;
        graph.setNodeAttribute(n, "x", Math.cos(angle) * 20);
        graph.setNodeAttribute(n, "y", Math.sin(angle) * 20);
      });
    } else {
      // Tree: same phyllotaxis as initial layout
      const co: Record<string, string[]> = {};
      graph.forEachEdge((_e, attrs, src, tgt) => {
        if (attrs.edgeType === "CONTAINS") (co[src] = co[src] ?? []).push(tgt);
      });
      const childSet = new Set(Object.values(co).flat());
      const rts = graph.nodes().filter(n => !childSet.has(n));
      const g2 = Math.PI * (3 - Math.sqrt(5));
      const orb = (n: number) => Math.max(25, Math.sqrt(n) * 12);
      function place(id: string, cx: number, cy: number, sc: number) {
        graph.setNodeAttribute(id, "x", cx);
        graph.setNodeAttribute(id, "y", cy);
        const kids = co[id] ?? [];
        if (!kids.length) return;
        const r = orb(kids.length) * sc;
        kids.forEach((k, i) => {
          const a = (i / kids.length) * 2 * Math.PI - Math.PI / 2;
          place(k, cx + Math.cos(a) * r, cy + Math.sin(a) * r, 0.45);
        });
      }
      rts.forEach((root, idx) => {
        const r = Math.sqrt(idx + 0.5) * (90 + orb((co[root] ?? []).length) * 0.4);
        const a = idx * g2;
        place(root, Math.cos(a) * r, Math.sin(a) * r, 1);
      });
    }
    sigmaRef.current?.scheduleRefresh();
  }, []);

  useEffect(() => {
    applyLayout(filter.layout);
  }, [filter.layout, applyLayout]);

  function zoomIn()  { sigmaRef.current?.getCamera().animatedZoom({ duration: 200 }); }
  function zoomOut() { sigmaRef.current?.getCamera().animatedUnzoom({ duration: 200 }); }
  function fitGraph() { sigmaRef.current?.getCamera().animatedReset({ duration: 300 }); }
  function resetLayout() { applyLayout(filter.layout); }

  return (
    <div className="flex-1 flex overflow-hidden">
      <FilterPanel state={filter} onChange={setFilter} />

      <div className="flex-1 relative overflow-hidden">
        {/* Search */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="bg-card border border-border rounded-lg px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-ring w-56"
          />
        </div>

        {/* Sigma canvas */}
        <div ref={containerRef} className="absolute inset-0" />

        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
            Loading graph…
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center px-6">
            <p className="text-sm font-medium text-foreground">No graph data</p>
            <p className="text-xs text-muted-foreground">
              Run{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                compass index ./repo
              </code>{" "}
              first.
            </p>
          </div>
        )}

        {/* Toolbar */}
        <div className="absolute bottom-4 left-4 flex gap-1.5 z-10">
          {[
            { label: "+", action: zoomIn,      title: "Zoom in" },
            { label: "−", action: zoomOut,     title: "Zoom out" },
            { label: "⊡", action: fitGraph,    title: "Fit to screen" },
            { label: "↺", action: resetLayout, title: "Reset layout" },
          ].map(({ label, action, title }) => (
            <button
              key={label}
              onClick={action}
              title={title}
              className="size-8 bg-card border border-border rounded-lg text-muted-foreground hover:text-foreground text-sm font-semibold transition-colors"
            >
              {label}
            </button>
          ))}
        </div>

        {/* Node click popover */}
        {popover && (
          <div
            className="fixed z-20 bg-card border border-border rounded-lg shadow-lg p-3 text-xs pointer-events-none"
            style={{ left: popover.x + 12, top: popover.y - 8 }}
          >
            <p className="font-semibold text-foreground mb-1">{popover.label}</p>
            <p className="text-muted-foreground">{popover.nodeType}</p>
            <p className="font-mono text-[10px] text-muted-foreground mt-1 max-w-[200px] truncate">
              {popover.filePath}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
