import type { BarRow } from "../charts/HorizontalBars";
import type { DonutSegment } from "../charts/Donut";
import type { HeatColumn, HeatRow } from "../charts/Heatmap";
import type { CallResolution } from "@/lib/api";
import type { HealthIssue } from "../IndexHealth";
import { NEUTRAL_COLOR, SERIES_COLORS } from "../charts/palette";
import type { TrendSeries } from "../charts/Trend";
import type {
  AiAuthorshipSignal,
  DeadCodeSignal,
  OwnershipSignal,
  RefactorEntry,
  RefactorSignal,
} from "./types";

/** Percentage rounded to one decimal; 0 when the whole is 0. */
export function percentOf(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 1000) / 10 : 0;
}

export function unusedTotal(d: DeadCodeSignal): number {
  return d.byKind.reduce((sum, k) => sum + k.unused, 0);
}

// Colour follows the entity: these three keep the kind colours used on the graph, in the order
// that was validated (function, method, class).
const KIND_SEGMENT = {
  function: { label: "Unused functions", color: SERIES_COLORS[0] },
  method: { label: "Unused methods", color: SERIES_COLORS[1] },
  class: { label: "Unused classes", color: SERIES_COLORS[2] },
} as const;

/** Unused symbols by kind, plus everything still in use as the neutral remainder. */
export function deadCodeSegments(d: DeadCodeSignal): ReadonlyArray<DonutSegment> {
  const order = ["function", "method", "class"] as const;
  const unused = order.map((kind) => ({
    id: kind,
    label: KIND_SEGMENT[kind].label,
    value: d.byKind.find((k) => k.kind === kind)?.unused ?? 0,
    color: KIND_SEGMENT[kind].color,
  }));
  return [
    ...unused,
    { id: "in-use", label: "In use", value: Math.max(0, d.totalSymbols - unusedTotal(d)), color: NEUTRAL_COLOR },
  ];
}

export function deadCodeFileBars(d: DeadCodeSignal): ReadonlyArray<BarRow> {
  return [...d.topFiles]
    .sort((a, b) => b.unused - a.unused)
    .map((f) => ({ id: f.path, label: f.path, value: f.unused, detail: `${f.unused} of ${f.total}` }));
}

export function refactorFileBars(files: ReadonlyArray<RefactorEntry>): ReadonlyArray<BarRow> {
  return [...files]
    .sort((a, b) => b.commits - a.commits)
    .map((f) => ({
      id: f.path,
      label: f.path,
      value: f.commits,
      detail: `${f.commits}`,
    }));
}

/** Commits per month for the busiest areas, one line each (at most four, the validated slots). */
export function refactorTrend(r: RefactorSignal): ReadonlyArray<TrendSeries> {
  return r.activity.areas.slice(0, 4).map((a, i) => ({
    id: a.path.replace(/\W+/g, "-"),
    label: a.path,
    color: SERIES_COLORS[i],
    values: a.commits,
  }));
}

export function aiShare(a: AiAuthorshipSignal): number {
  return percentOf(
    a.agents.reduce((sum, g) => sum + g.lines, 0),
    a.totalLines,
  );
}

/** Agents beyond the validated slots are folded into one "Other agents" segment. */
const MAX_NAMED_AGENTS = 4;

export function agentSegments(a: AiAuthorshipSignal): ReadonlyArray<DonutSegment> {
  const named = a.agents.slice(0, MAX_NAMED_AGENTS);
  const rest = a.agents.slice(MAX_NAMED_AGENTS).reduce((sum, g) => sum + g.lines, 0);
  const agentLines = a.agents.reduce((sum, g) => sum + g.lines, 0);
  return [
    ...named.map((g, i) => ({ id: g.name, label: g.name, value: g.lines, color: SERIES_COLORS[i] })),
    ...(rest > 0
      ? [{ id: "other-agents", label: "Other agents", value: rest, color: "var(--kind-external)" }]
      : []),
    { id: "people", label: "Written by people", value: Math.max(0, a.totalLines - agentLines), color: NEUTRAL_COLOR },
  ];
}

export function aiTrend(a: AiAuthorshipSignal): ReadonlyArray<TrendSeries> {
  return [{ id: "ai", label: "AI-written lines", color: "var(--kind-file)", values: a.history.percent }];
}

/** Heatmap input: people first, then agents, each ordered by their total share. */
export function ownershipMatrix(o: OwnershipSignal): { columns: HeatColumn[]; rows: HeatRow[] } {
  const totals = new Map<string, { kind: "person" | "agent"; total: number }>();
  for (const area of o.areas) {
    for (const owner of area.owners) {
      const t = totals.get(owner.name) ?? { kind: owner.kind, total: 0 };
      t.total += owner.percent;
      totals.set(owner.name, t);
    }
  }
  const columns = [...totals.entries()]
    .sort(([, a], [, b]) => (a.kind === b.kind ? b.total - a.total : a.kind === "person" ? -1 : 1))
    .map(([name, t]) => ({ id: name, label: name, kind: t.kind }));
  const rows = o.areas.map((area) => ({
    id: area.path,
    label: area.path,
    values: Object.fromEntries(area.owners.map((x) => [x.name, x.percent])),
  }));
  return { columns, rows };
}

/** Share of calls resolved; 100 when the code makes no calls, since nothing is missing. */
export function resolvedCallPercent(c: CallResolution): number {
  return c.total > 0 ? percentOf(c.resolved, c.total) : 100;
}

/** What the index could not resolve; amber because results are degraded, not failed. */
export function healthIssues(c: CallResolution): ReadonlyArray<HealthIssue> {
  return [
    { id: "unresolved", label: "Unresolved calls", count: c.total - c.resolved, dotClass: "bg-kind-class" },
  ];
}
