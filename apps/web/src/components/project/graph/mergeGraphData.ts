import type { VisibleNode, VisibleEdge } from "./useExpandableGraph";

// force-graph / 3d-force-graph mutate node objects in place to store simulation
// state (x, y, z, vx, vy...). Passing brand-new node objects on every update would
// wipe that state and re-layout the whole graph each time a node is expanded, so
// we keep a persistent object per node id and only add/remove as visibility changes.
export function mergeGraphData(
  nodeCache: Map<string, VisibleNode>,
  nodes: VisibleNode[],
  edges: VisibleEdge[]
) {
  const nextIds = new Set(nodes.map((n) => n.id));
  for (const id of nodeCache.keys()) {
    if (!nextIds.has(id)) nodeCache.delete(id);
  }
  const outNodes = nodes.map((n) => {
    const existing = nodeCache.get(n.id);
    if (existing) {
      Object.assign(existing, n);
      return existing;
    }
    nodeCache.set(n.id, n);
    return n;
  });
  const outLinks = edges.map((e) => ({ ...e }));
  return { nodes: outNodes, links: outLinks };
}
