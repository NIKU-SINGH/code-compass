import type { LucideIcon } from "lucide-react";
import { Box, Braces, FileInput, FileText, Network, Package, PhoneIncoming, Target } from "lucide-react";
import { symbolLocation } from "@/components/impact/symbolKind";
import type { EdgeType, IndexCounts, OverviewResult, RankedSymbol, SymbolKind } from "@/lib/api";

/** One row of an insight card. `barPercent` is 0-100, relative to the card's maximum. */
export interface InsightRowData {
  id: string;
  name: string;
  location: string;
  metric: string;
  barPercent: number;
  kind: SymbolKind;
}

/** View-model of one insight card; `navigateTo` is the view a row click opens (null = rows are not clickable). */
export interface InsightCardData {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  rows: ReadonlyArray<InsightRowData>;
  emptyText: string;
  navigateTo: "impact" | "graph" | null;
}

export interface StatTileData {
  id: string;
  label: string;
  value: number;
  icon: LucideIcon;
}

export interface BreakdownSegment {
  id: string;
  label: string;
  value: number;
  /** 0-100, relative to the largest segment. */
  barPercent: number;
  /** Tailwind background class from the `--kind-*` / `--edge-*` tokens. */
  colorClass: string;
}

/** value / max as a percentage; 0 when the maximum is 0. */
export function barPercent(value: number, max: number): number {
  return max > 0 ? (value / max) * 100 : 0;
}

function plural(count: number, one: string, many: string): string {
  return `${count.toLocaleString()} ${count === 1 ? one : many}`;
}

function rankedRows(
  items: ReadonlyArray<RankedSymbol>,
  metric: (count: number) => string,
): ReadonlyArray<InsightRowData> {
  const max = Math.max(0, ...items.map((i) => i.count));
  return items.map((i) => ({
    id: i.symbol.id,
    name: i.symbol.name,
    location: symbolLocation(i.symbol),
    metric: metric(i.count),
    barPercent: barPercent(i.count, max),
    kind: i.symbol.kind,
  }));
}

export function riskiestCard(r: OverviewResult): InsightCardData {
  return {
    id: "riskiest",
    title: "Riskiest to change",
    description: "Symbols whose change reaches the most others",
    icon: Target,
    rows: rankedRows(r.riskiest_to_change, (n) => `${n.toLocaleString()} affected`),
    emptyText: "No resolved calls yet",
    navigateTo: "impact",
  };
}

export function mostImportedCard(r: OverviewResult): InsightCardData {
  return {
    id: "most-imported",
    title: "Most imported files",
    description: "Files imported by the most other files",
    icon: FileInput,
    rows: rankedRows(r.most_imported_files, (n) => plural(n, "importer", "importers")),
    emptyText: "No imports found",
    navigateTo: "graph",
  };
}

export function mostCalledCard(r: OverviewResult): InsightCardData {
  return {
    id: "most-called",
    title: "Most called functions",
    description: "Functions with the most distinct callers",
    icon: PhoneIncoming,
    rows: rankedRows(r.most_called_functions, (n) => plural(n, "caller", "callers")),
    emptyText: "No resolved calls yet",
    navigateTo: "graph",
  };
}

export function librariesCard(r: OverviewResult): InsightCardData {
  const max = Math.max(0, ...r.top_external_libraries.map((l) => l.call_count));
  return {
    id: "libraries",
    title: "External libraries",
    description: "Third-party packages your code calls most",
    icon: Package,
    rows: r.top_external_libraries.map((l) => ({
      id: l.library,
      name: l.library,
      location: "",
      metric: plural(l.call_count, "call", "calls"),
      barPercent: barPercent(l.call_count, max),
      kind: "external" as const,
    })),
    emptyText: "No external calls found",
    navigateTo: null,
  };
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

function segments(
  defs: ReadonlyArray<{ id: string; label: string; value: number; colorClass: string }>,
): ReadonlyArray<BreakdownSegment> {
  const max = Math.max(0, ...defs.map((d) => d.value));
  return defs.map((d) => ({ ...d, barPercent: barPercent(d.value, max) }));
}

export function kindBreakdown(counts: IndexCounts): ReadonlyArray<BreakdownSegment> {
  return segments([
    { id: "files", label: "Files", value: counts.files, colorClass: "bg-kind-file" },
    { id: "classes", label: "Classes", value: counts.classes, colorClass: "bg-kind-class" },
    { id: "functions", label: "Functions", value: counts.functions, colorClass: "bg-kind-function" },
  ]);
}

export function edgeBreakdown(counts: IndexCounts): ReadonlyArray<BreakdownSegment> {
  return segments([
    { id: "CONTAINS", label: "Contains", value: edgeCount(counts, "CONTAINS"), colorClass: "bg-edge-contains" },
    { id: "IMPORTS", label: "Imports", value: edgeCount(counts, "IMPORTS"), colorClass: "bg-edge-imports" },
    { id: "INHERITS", label: "Inherits", value: edgeCount(counts, "INHERITS"), colorClass: "bg-edge-inherits" },
    { id: "CALLS", label: "Calls", value: edgeCount(counts, "CALLS"), colorClass: "bg-edge-calls" },
    { id: "CALLS_EXTERN", label: "Calls (external)", value: edgeCount(counts, "CALLS_EXTERN"), colorClass: "bg-edge-external" },
  ]);
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
