import { describe, expect, it } from "vitest";
import type { IndexCounts } from "@/lib/api";
import { compositionEdges, compositionSegments } from "@/components/overview/insightCards";
import { healthIssues, resolvedCallPercent } from "@/components/overview/signals/cards";
import { SAMPLE_INDEX_HEALTH } from "@/components/overview/signals/sampleData";

const counts: IndexCounts = {
  files: 15,
  classes: 8,
  functions: 27,
  edges_by_type: { CONTAINS: 35, IMPORTS: 22, INHERITS: 3, CALLS: 31, CALLS_EXTERN: 7 },
};

describe("composition", () => {
  it("shows files, classes and functions with their counts", () => {
    expect(compositionSegments(counts).map((s) => [s.label, s.value])).toEqual([
      ["Files", 15],
      ["Classes", 8],
      ["Functions", 27],
    ]);
  });

  it("lists all five edge types, scaled against the busiest", () => {
    const edges = compositionEdges(counts);
    expect(edges.map((e) => e.label)).toEqual(["Contains", "Imports", "Inherits", "Calls", "Ext. calls"]);
    expect(edges[0].barPercent).toBe(100);
    expect(edges[2].barPercent).toBeCloseTo((3 / 35) * 100);
  });

  it("keeps edge types that are missing from the index at zero", () => {
    const edges = compositionEdges({ ...counts, edges_by_type: { CONTAINS: 4 } });
    expect(edges.find((e) => e.id === "CALLS")).toMatchObject({ value: 0, barPercent: 0 });
  });
});

describe("index health", () => {
  it("derives the resolved share and unresolved count from the same totals", () => {
    expect(resolvedCallPercent(SAMPLE_INDEX_HEALTH)).toBe(88.6);
    const [unresolved] = healthIssues(SAMPLE_INDEX_HEALTH);
    expect(unresolved.count).toBe(SAMPLE_INDEX_HEALTH.totalCalls - SAMPLE_INDEX_HEALTH.resolvedCalls);
  });

  it("marks a parse failure as an error and the rest as degraded", () => {
    const dots = healthIssues(SAMPLE_INDEX_HEALTH).map((i) => i.dotClass);
    expect(dots).toEqual(["bg-kind-class", "bg-kind-class", "bg-kind-external"]);
  });
});
