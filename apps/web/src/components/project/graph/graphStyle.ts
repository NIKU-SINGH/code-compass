import type { NodeType, EdgeType } from "./useGraphData";

export const NODE_COLOR: Record<NodeType, string> = {
  File: "#60a5fa",
  Class: "#fb923c",
  Function: "#4ade80",
  Method: "#c084fc",
  ExternalDep: "#f87171",
  Field: "#e879f9",
};

export const NODE_LABEL: Record<NodeType, string> = {
  File: "File",
  Class: "Class",
  Function: "Function",
  Method: "Method",
  ExternalDep: "External Dep",
  Field: "Field",
};

export const NODE_SIZE: Record<NodeType, number> = {
  File: 8,
  Class: 6,
  Function: 4,
  Method: 4,
  ExternalDep: 3,
  Field: 3,
};

export const EDGE_COLOR: Record<EdgeType, string> = {
  CONTAINS: "rgba(251,146,60,0.55)",
  IMPORTS: "#60a5fa",
  INHERITS: "#fb923c",
  CALLS: "rgba(255,255,255,0.12)",
  CALLS_EXTERN: "#f87171",
};

export const EDGE_LABEL: Record<EdgeType, string> = {
  CONTAINS: "Contains",
  IMPORTS: "Imports",
  INHERITS: "Inherits",
  CALLS: "Calls",
  CALLS_EXTERN: "Ext. Calls",
};

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

// File nodes dominate most repos and all share the same NODE_COLOR, so a
// graph made only of files would render as one flat color. Vary the hue by
// top-level directory instead, so modules are visually distinguishable even
// when entity-type diversity is low. Non-file types keep their fixed color.
export function colorForNode(filePath: string, type: NodeType): string {
  if (type !== "File") return NODE_COLOR[type];
  const dir = filePath.split("/").slice(0, -1).join("/") || filePath;
  const hue = hashString(dir) % 360;
  return `hsl(${hue}, 62%, 62%)`;
}
