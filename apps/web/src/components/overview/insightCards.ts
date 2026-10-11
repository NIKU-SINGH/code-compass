import type { LucideIcon } from "lucide-react";
import { Box, Braces, FileText, Network } from "lucide-react";
import type { EdgeType, IndexCounts, OverviewResult } from "@/lib/api";
import type { CompositionEdge, CompositionSegment } from "./GraphComposition";

export interface StatTileData {
  id: string;
  label: string;
  value: number;
  icon: LucideIcon;
}

/** value / max as a percentage; 0 when the maximum is 0. */
export function barPercent(value: number, max: number): number {
  return max > 0 ? (value / max) * 100 : 0;
}

function edgeCount(counts: IndexCounts, type: EdgeType): number {
  return counts.edges_by_type[type] ?? 0;
}

export function totalEdges(counts: IndexCounts): number {
  return Object.values(counts.edges_by_type).reduce((sum, n) => sum + n, 0);
}

export function statTiles(counts: IndexCounts): ReadonlyArray<StatTileData> {
  return [
    { id: "files", label: "Files", value: counts.files, icon: FileText },
    { id: "classes", label: "Classes", value: counts.classes, icon: Box },
    { id: "functions", label: "Functions", value: counts.functions, icon: Braces },
    { id: "edges", label: "Edges", value: totalEdges(counts), icon: Network },
  ];
}

/** Node mix for the composition bar. Functions include methods, so there is no separate method slice. */
export function compositionSegments(counts: IndexCounts): ReadonlyArray<CompositionSegment> {
  return [
    { id: "files", label: "Files", value: counts.files, colorClass: "bg-kind-file" },
    { id: "classes", label: "Classes", value: counts.classes, colorClass: "bg-kind-class" },
    { id: "functions", label: "Functions", value: counts.functions, colorClass: "bg-kind-function" },
  ];
}

const EDGE_ROWS: ReadonlyArray<{ type: EdgeType; label: string; colorClass: string }> = [
  { type: "CONTAINS", label: "Contains", colorClass: "bg-edge-contains" },
  { type: "IMPORTS", label: "Imports", colorClass: "bg-edge-imports" },
  { type: "INHERITS", label: "Inherits", colorClass: "bg-edge-inherits" },
  { type: "CALLS", label: "Calls", colorClass: "bg-edge-calls" },
  { type: "CALLS_EXTERN", label: "Ext. calls", colorClass: "bg-edge-external" },
];

/** Every edge type with its count and a bar relative to the busiest type. */
export function compositionEdges(counts: IndexCounts): ReadonlyArray<CompositionEdge> {
  const max = Math.max(0, ...EDGE_ROWS.map((r) => edgeCount(counts, r.type)));
  return EDGE_ROWS.map((r) => ({
    id: r.type,
    label: r.label,
    value: edgeCount(counts, r.type),
    colorClass: r.colorClass,
    barPercent: barPercent(edgeCount(counts, r.type), max),
  }));
}

/**
 * Freshness line: "Indexed {date} · {short commit} · {n} changed since".
 * `now` is injectable for testing.
 */
export function freshnessText(
  index: OverviewResult["index"],
  now: Date = new Date(),
): string {
  const parts = [`Indexed ${relativeTime(new Date(index.indexed_at), now)}`];
  if (index.indexed_commit) parts.push(index.indexed_commit.slice(0, 7));
  if (index.stale_file_count > 0) parts.push(`${index.stale_file_count.toLocaleString()} changed since`);
  return parts.join(" · ");
}

export function relativeTime(then: Date, now: Date): string {
  const ms = then.getTime();
  if (Number.isNaN(ms)) return "at an unknown time";
  const sec = Math.max(0, Math.round((now.getTime() - ms) / 1000));
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} d ago`;
  return then.toLocaleDateString();
}
