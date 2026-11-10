"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

type GraphMap = components["schemas"]["GraphMap"];
type MapNode = components["schemas"]["MapNode"];
type MapEdge = components["schemas"]["MapEdge"];

/** Display type of a node in the graph view (legend, colours, sizes). */
export type NodeType = "File" | "Class" | "Function" | "Method" | "ExternalDep";
export type EdgeType = components["schemas"]["EdgeType"];

/** A map node as the graph view draws it: the API node with its display type. */
export type ApiNode = Omit<MapNode, "kind"> & { type: NodeType };
/** A map edge with the id the 3D view keys its links by. */
export type ApiEdge = MapEdge & { id: string };

export interface GraphData {
  nodes: ApiNode[];
  edges: ApiEdge[];
}

const NODE_TYPE: Record<MapNode["kind"], NodeType> = {
  file: "File",
  class: "Class",
  function: "Function",
  method: "Method",
  external: "ExternalDep",
};

/** Adapt the API's graph map to the graph view's shape; edge ids are their position. */
export function toGraphData(map: GraphMap): GraphData {
  return {
    nodes: map.nodes.map(({ kind, ...node }) => ({ ...node, type: NODE_TYPE[kind] })),
    edges: map.edges.map((edge, index) => ({ ...edge, id: `e${index}` })),
  };
}

export function useGraphData() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<GraphMap>("/api/graph/map")
      .then((map) => {
        if (cancelled) return;
        setData(toGraphData(map));
        setLoading(false);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error };
}
