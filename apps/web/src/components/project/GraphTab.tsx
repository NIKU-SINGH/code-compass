"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { circular } from "graphology-layout";
import { apiFetch } from "@/lib/api";
import {
  FilterPanel,
  FilterState,
  DEFAULT_FILTER_STATE,
  NodeType,
  EdgeType,
} from "./FilterPanel";

const NODE_COLOR: Record<NodeType, string> = {
  File:        "oklch(0.588 0.217 264)",
  Class:       "#f59e0b",
  Function:    "#10b981",
  Method:      "#06b6d4",
  ExternalDep: "#94a3b8",
  Field:       "#a78bfa",
};

const NODE_SIZE: Record<NodeType, number> = {
  File:        12,
  Class:       9,
  Function:    6,
  Method:      6,
  ExternalDep: 5,
  Field:       5,
};

const EDGE_COLOR: Record<EdgeType, string> = {
  CONTAINS:    "#10b981",
  IMPORTS:     "oklch(0.588 0.217 264)",
  INHERITS:    "#f97316",
  CALLS:       "rgba(255,255,255,0.15)",
  CALLS_EXTERN:"#94a3b8",
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

    let sigma: Sigma | null = null;

    apiFetch<GraphData>("/api/repo/graph")
      .then((data) => {
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
              color:    EDGE_COLOR[e.type as EdgeType] ?? "rgba(255,255,255,0.15)",
              size:     1,
            });
          } catch {
            // skip duplicate or missing-node edges
          }
        });

        circular.assign(graph);
        forceAtlas2.assign(graph, { iterations: 100, settings: { gravity: 1 } });

        graphRef.current = graph;

        sigma = new Sigma(graph, containerRef.current!, {
          renderEdgeLabels: false,
          defaultEdgeColor: "rgba(255,255,255,0.15)",
          defaultNodeColor: "#6b7280",
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
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setLoading(false);
      });

    return () => {
      sigma?.kill();
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

    sigmaRef.current?.refresh();
  }, [filter]);

  // Apply label visibility
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.forEachNode((node, attrs) => {
      graph.setNodeAttribute(node, "label", filter.showLabels ? (attrs.label as string) : "");
    });
    sigmaRef.current?.refresh();
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

    sigmaRef.current?.refresh();
  }, [search, filter.nodes]);

  // Layout switching
  const applyLayout = useCallback((layout: FilterState["layout"]) => {
    const graph = graphRef.current;
    if (!graph) return;
    if (layout === "force") {
      forceAtlas2.assign(graph, { iterations: 100, settings: { gravity: 1 } });
    } else {
      circular.assign(graph);
    }
    sigmaRef.current?.refresh();
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
        <div ref={containerRef} className="w-full h-full" />

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
