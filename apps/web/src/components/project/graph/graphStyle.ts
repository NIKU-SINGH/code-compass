import { resolveCssColor } from "@/lib/cssColor";
import type { NodeType, EdgeType } from "./useGraphData";

const NODE_TOKEN: Record<NodeType, string> = {
  File: "--kind-file",
  Class: "--kind-class",
  Function: "--kind-function",
  Method: "--kind-method",
  ExternalDep: "--kind-external",
};

const EDGE_TOKEN: Record<EdgeType, string> = {
  CONTAINS: "--edge-contains",
  IMPORTS: "--edge-imports",
  INHERITS: "--edge-inherits",
  CALLS: "--edge-calls",
  CALLS_EXTERN: "--edge-external",
};

/** Tailwind background classes (static strings so Tailwind keeps them) for legend swatches. */
export const NODE_DOT_CLASS: Record<NodeType, string> = {
  File: "bg-kind-file",
  Class: "bg-kind-class",
  Function: "bg-kind-function",
  Method: "bg-kind-method",
  ExternalDep: "bg-kind-external",
};

export const NODE_TEXT_CLASS: Record<NodeType, string> = {
  File: "text-kind-file",
  Class: "text-kind-class",
  Function: "text-kind-function",
  Method: "text-kind-method",
  ExternalDep: "text-kind-external",
};

export const EDGE_LINE_CLASS: Record<EdgeType, string> = {
  CONTAINS: "bg-edge-contains",
  IMPORTS: "bg-edge-imports",
  INHERITS: "bg-edge-inherits",
  CALLS: "bg-edge-calls",
  CALLS_EXTERN: "bg-edge-external",
};

export const NODE_LABEL: Record<NodeType, string> = {
  File: "File",
  Class: "Class",
  Function: "Function",
  Method: "Method",
  ExternalDep: "External Dep",
};

export const NODE_SIZE: Record<NodeType, number> = {
  File: 8,
  Class: 6,
  Function: 4,
  Method: 4,
  ExternalDep: 3,
};

export const EDGE_LABEL: Record<EdgeType, string> = {
  CONTAINS: "Contains",
  IMPORTS: "Imports",
  INHERITS: "Inherits",
  CALLS: "Calls",
  CALLS_EXTERN: "Ext. Calls",
};

/** `#rrggbb` for a node kind, for THREE.js. */
export function colorForNode(type: NodeType): string {
  return resolveCssColor(NODE_TOKEN[type] ?? "--kind-file");
}

/** `#rrggbb` for an edge type, for THREE.js. */
export function colorForEdge(type: EdgeType): string {
  return resolveCssColor(EDGE_TOKEN[type] ?? "--edge-contains");
}
