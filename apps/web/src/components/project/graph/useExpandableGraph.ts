"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import type { GraphData, NodeType, EdgeType } from "./useGraphData";

export interface VisibleNode {
  id: string;
  label: string;
  type: NodeType;
  filePath: string;
  hasChildren: boolean;
  expanded: boolean;
}
export interface VisibleEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

export function useExpandableGraph(data: GraphData | null) {
  const [revealed, setRevealed] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [typeVisibility, setTypeVisibility] = useState<Record<NodeType, boolean>>({
    File: true,
    Class: true,
    Function: true,
    Method: true,
    ExternalDep: true,
  });
  const [edgeTypeVisibility, setEdgeTypeVisibility] = useState<Record<EdgeType, boolean>>({
    CONTAINS: true,
    IMPORTS: true,
    INHERITS: true,
    CALLS: true,
    CALLS_EXTERN: true,
  });

  // childrenOf/parentOf drive expand() and search's revealPathTo, and walk
  // both CONTAINS (File -> Class/Function -> ...) and IMPORTS (File -> File)
  // so double-clicking a file can surface what it imports too. Root
  // determination for the *initial* view is deliberately CONTAINS-only:
  // files are never CONTAINS targets, so every file (and the IMPORTS edges
  // between them) is visible from the start, while the finer-grained
  // classes/functions inside each file stay collapsed until expanded. Using
  // IMPORTS for roots too would hide most import edges by default, since an
  // imported file would no longer count as a root.
  const { childrenOf, parentOf, roots } = useMemo(() => {
    const childrenOf: Record<string, string[]> = {};
    const parentOf: Record<string, string> = {};
    const containsParentOf: Record<string, string> = {};
    if (data) {
      for (const e of data.edges) {
        if (e.type === "CONTAINS" || e.type === "IMPORTS") {
          (childrenOf[e.source] ??= []).push(e.target);
          if (!(e.target in parentOf)) parentOf[e.target] = e.source;
        }
        if (e.type === "CONTAINS") {
          containsParentOf[e.target] = e.source;
        }
      }
    }
    const roots = data ? data.nodes.filter((n) => !containsParentOf[n.id]).map((n) => n.id) : [];
    return { childrenOf, parentOf, roots };
  }, [data]);

  // Reset to root-only whenever a new graph loads
  useEffect(() => {
    setRevealed(new Set(roots));
    setExpanded(new Set());
  }, [roots]);

  const expand = useCallback(
    (nodeId: string) => {
      const kids = childrenOf[nodeId];
      if (!kids || kids.length === 0) return;
      setRevealed((prev) => {
        const next = new Set(prev);
        kids.forEach((k) => next.add(k));
        return next;
      });
      setExpanded((prev) => new Set(prev).add(nodeId));
    },
    [childrenOf]
  );

  const revealPathTo = useCallback(
    (nodeId: string) => {
      const chain: string[] = [];
      const seen = new Set<string>();
      let cur: string | undefined = nodeId;
      // IMPORTS edges can cycle (A imports B, B imports A), unlike the
      // strictly-hierarchical CONTAINS edges this originally walked — guard
      // against looping forever chasing parentOf around a cycle.
      while (cur && !seen.has(cur)) {
        seen.add(cur);
        chain.push(cur);
        cur = parentOf[cur];
      }
      setRevealed((prev) => {
        const next = new Set(prev);
        chain.forEach((id) => next.add(id));
        return next;
      });
      setExpanded((prev) => {
        const next = new Set(prev);
        chain.slice(1).forEach((id) => next.add(id));
        return next;
      });
    },
    [parentOf]
  );

  const toggleType = useCallback((type: NodeType) => {
    setTypeVisibility((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  const toggleEdgeType = useCallback((type: EdgeType) => {
    setEdgeTypeVisibility((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  const nodeById = useMemo(() => {
    const map = new Map<string, GraphData["nodes"][number]>();
    data?.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [data]);

  const visibleNodes = useMemo<VisibleNode[]>(() => {
    const out: VisibleNode[] = [];
    revealed.forEach((id) => {
      const n = nodeById.get(id);
      if (!n) return;
      const type = n.type as NodeType;
      if (!typeVisibility[type]) return;
      out.push({
        id: n.id,
        label: n.label,
        type,
        filePath: n.file_path,
        hasChildren: (childrenOf[id]?.length ?? 0) > 0,
        expanded: expanded.has(id),
      });
    });
    return out;
  }, [revealed, nodeById, typeVisibility, childrenOf, expanded]);

  const visibleEdges = useMemo<VisibleEdge[]>(() => {
    if (!data) return [];
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    return data.edges
      .filter(
        (e) =>
          visibleIds.has(e.source) &&
          visibleIds.has(e.target) &&
          edgeTypeVisibility[e.type as EdgeType]
      )
      .map((e) => ({ id: e.id, source: e.source, target: e.target, type: e.type }));
  }, [data, visibleNodes, edgeTypeVisibility]);

  const typeCounts = useMemo(() => {
    const counts: Record<NodeType, number> = {
      File: 0,
      Class: 0,
      Function: 0,
      Method: 0,
      ExternalDep: 0,
    };
    revealed.forEach((id) => {
      const n = nodeById.get(id);
      if (n) counts[n.type as NodeType]++;
    });
    return counts;
  }, [revealed, nodeById]);

  const edgeTypeCounts = useMemo(() => {
    const counts: Record<EdgeType, number> = {
      CONTAINS: 0,
      IMPORTS: 0,
      INHERITS: 0,
      CALLS: 0,
      CALLS_EXTERN: 0,
    };
    if (!data) return counts;
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    data.edges.forEach((e) => {
      if (visibleIds.has(e.source) && visibleIds.has(e.target)) {
        counts[e.type as EdgeType]++;
      }
    });
    return counts;
  }, [data, visibleNodes]);

  return {
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
  };
}
