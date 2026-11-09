import { describe, expect, it } from "vitest";
import type { CallResolution, IndexCounts } from "@/lib/api";
import { compositionEdges, compositionSegments, indexFreshness, statTiles } from "@/components/overview/insightCards";
import { healthIssues, resolvedCallPercent } from "@/components/overview/signals/cards";

const calls: CallResolution = { total: 193, resolved: 171 };

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
    expect(resolvedCallPercent(calls)).toBe(88.6);
    const [unresolved] = healthIssues(calls);
    expect(unresolved.count).toBe(22);
  });

  it("reads as fully resolved when the code makes no calls", () => {
    expect(resolvedCallPercent({ total: 0, resolved: 0 })).toBe(100);
  });
});

describe("stat tiles", () => {
  it("gives every tile a label, a description and a legend colour", () => {
    const tiles = statTiles(counts);
    expect(tiles.map((t) => [t.label, t.value])).toEqual([
      ["Files", 15],
      ["Classes", 8],
      ["Functions", 27],
      ["Edges", 98],
    ]);
    for (const t of tiles) {
      expect(t.detail).not.toBe("");
      expect(t.colorClass).toMatch(/^bg-(kind|edge)-/);
    }
  });
});

describe("index freshness", () => {
  const now = new Date("2026-01-01T12:00:00Z");
  const index = {
    indexed_at: "2026-01-01T11:55:00Z",
    indexed_commit: "abcdef1234567",
    stale_file_count: 3,
    repo_root: "/repo",
  } as Parameters<typeof indexFreshness>[0];

  it("splits the header facts into indexed time, short commit and stale count", () => {
    expect(indexFreshness(index, now)).toEqual({ indexed: "Indexed 5 min ago", commit: "abcdef1", staleCount: 3 });
  });

  it("omits the commit when the index has none", () => {
    expect(indexFreshness({ ...index, indexed_commit: null }, now).commit).toBeUndefined();
  });
});
