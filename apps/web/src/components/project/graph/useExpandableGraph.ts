"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import type { GraphData, NodeType, EdgeType } from "./useGraphData";

/** How much of a node type is on the globe; see `useExpandableGraph`. */
export type TypeMode = "off" | "revealed" | "all";

export interface VisibleNode {
  id: string;
  publicId: string;
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
  // Per node type: "all" shows every node of the type, "revealed" only those brought in by
  // expanding or searching, "off" none. Only files are on the globe to begin with.
  const [typeMode, setTypeMode] = useState<Record<NodeType, TypeMode>>({
    File: "all",
    Class: "off",
    Function: "off",
    Method: "off",
    ExternalDep: "off",
  });
  const typeVisibility = useMemo(
    () => Object.fromEntries(Object.entries(typeMode).map(([t, m]) => [t, m !== "off"])) as Record<NodeType, boolean>,
    [typeMode]
  );
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

  const nodeById = useMemo(() => {
    const map = new Map<string, GraphData["nodes"][number]>();
    data?.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [data]);

  // Bringing nodes in by expanding or searching must show them, so their types switch on.
  const promoteTypesOf = useCallback(
    (ids: Iterable<string>) => {
      setTypeMode((prev) => {
        let next = prev;
        for (const id of ids) {
          const type = nodeById.get(id)?.type as NodeType | undefined;
          if (type && next[type] === "off") next = { ...next, [type]: "revealed" };
        }
        return next;
      });
    },
    [nodeById]
  );

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
      promoteTypesOf(kids);
    },
    [childrenOf, promoteTypesOf]
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
      promoteTypesOf(chain);
    },
    [parentOf, promoteTypesOf]
  );

  const toggleType = useCallback((type: NodeType) => {
    // Off -> everything of this type; on (all or partly) -> off.
    setTypeMode((prev) => ({ ...prev, [type]: prev[type] === "off" ? "all" : "off" }));
  }, []);

  const toggleEdgeType = useCallback((type: EdgeType) => {
    setEdgeTypeVisibility((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  const visibleNodes = useMemo<VisibleNode[]>(() => {
    const out: VisibleNode[] = [];
    data?.nodes.forEach((n) => {
      const type = n.type as NodeType;
      const mode = typeMode[type];
      if (mode === "off" || (mode === "revealed" && !revealed.has(n.id))) return;
      out.push({
        id: n.id,
        publicId: n.public_id,
        label: n.label,
        type,
        filePath: n.file_path,
        hasChildren: (childrenOf[n.id]?.length ?? 0) > 0,
        expanded: expanded.has(n.id),
      });
    });
    return out;
  }, [data, revealed, typeMode, childrenOf, expanded]);

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
    visibleNodes.forEach((n) => {
      counts[n.type]++;
    });
    return counts;
  }, [visibleNodes]);

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

  // Everything in the index per type, whether or not it is on the globe yet.
  const typeTotals = useMemo(() => {
    const totals: Record<NodeType, number> = { File: 0, Class: 0, Function: 0, Method: 0, ExternalDep: 0 };
    data?.nodes.forEach((n) => {
      totals[n.type as NodeType]++;
    });
    return totals;
  }, [data]);

  const edgeTypeTotals = useMemo(() => {
    const totals: Record<EdgeType, number> = { CONTAINS: 0, IMPORTS: 0, INHERITS: 0, CALLS: 0, CALLS_EXTERN: 0 };
    data?.edges.forEach((e) => {
      totals[e.type as EdgeType]++;
    });
    return totals;
  }, [data]);

  return {
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
  };
}
