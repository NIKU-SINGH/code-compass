"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type NodeType = "File" | "Class" | "Function" | "Method" | "ExternalDep";
export type EdgeType = "CONTAINS" | "IMPORTS" | "INHERITS" | "CALLS" | "CALLS_EXTERN";

export interface ApiNode {
  id: string;
  label: string;
  type: string;
  file_path: string;
}
export interface ApiEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}
export interface GraphData {
  nodes: ApiNode[];
  edges: ApiEdge[];
}

export function useGraphData() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch<GraphData>("/api/repo/graph")
      .then((d) => {
        if (cancelled) return;
        setData(d);
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
