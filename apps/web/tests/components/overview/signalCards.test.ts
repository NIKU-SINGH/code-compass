import { describe, expect, it } from "vitest";
import {
  agentSegments,
  aiShare,
  aiTrend,
  deadCodeFileBars,
  deadCodeSegments,
  ownershipMatrix,
  percentOf,
  refactorFileBars,
  refactorTrend,
  unusedTotal,
} from "@/components/overview/signals/cards";
import {
  SAMPLE_AI_AUTHORSHIP,
  SAMPLE_DEAD_CODE,
  SAMPLE_OWNERSHIP,
  SAMPLE_REFACTORING,
} from "@/components/overview/signals/sampleData";
import { SERIES_COLORS } from "@/components/overview/charts/palette";

describe("percentOf", () => {
  it("rounds to one decimal and tolerates an empty whole", () => {
    expect(percentOf(17, 149)).toBe(11.4);
    expect(percentOf(1, 3)).toBe(33.3);
    expect(percentOf(5, 0)).toBe(0);
  });
});

describe("dead code", () => {
  it("splits symbols into unused kinds plus an in-use remainder that covers every symbol", () => {
    expect(unusedTotal(SAMPLE_DEAD_CODE)).toBe(17);
    const segs = deadCodeSegments(SAMPLE_DEAD_CODE);
    expect(segs.map((s) => s.id)).toEqual(["function", "method", "class", "in-use"]);
    expect(segs.reduce((n, s) => n + s.value, 0)).toBe(SAMPLE_DEAD_CODE.totalSymbols);
  });

  it("ranks files by unused symbols, highest first", () => {
    const bars = deadCodeFileBars(SAMPLE_DEAD_CODE);
    expect(bars[0]).toMatchObject({ label: "app/legacy/exporters.py", value: 5, detail: "5 of 8" });
    const values = bars.map((b) => b.value);
    expect(values).toEqual([...values].sort((a, b) => b - a));
  });
});

describe("refactoring", () => {
  it("ranks files by commits", () => {
    const [first] = refactorFileBars(SAMPLE_REFACTORING.files);
    expect(first.value).toBe(38);
    expect(first.detail).toBe("38");
  });

  it("gives each area one value per month, in the validated colour slots", () => {
    const series = refactorTrend(SAMPLE_REFACTORING);
    expect(series).toHaveLength(4);
    for (const [i, s] of series.entries()) {
      expect(s.values).toHaveLength(SAMPLE_REFACTORING.activity.labels.length);
      expect(s.color).toBe(SERIES_COLORS[i]);
    }
    expect(new Set(series.map((s) => s.id)).size).toBe(series.length);
  });
});

describe("AI authorship", () => {
  it("derives the share from agent lines, and the trend ends on it", () => {
    expect(aiShare(SAMPLE_AI_AUTHORSHIP)).toBe(32.1);
    const [trend] = aiTrend(SAMPLE_AI_AUTHORSHIP);
    expect(trend.values[trend.values.length - 1]).toBe(32.1);
  });

  it("covers every line, with people as the remainder", () => {
    const segs = agentSegments(SAMPLE_AI_AUTHORSHIP);
    expect(segs.reduce((n, s) => n + s.value, 0)).toBe(SAMPLE_AI_AUTHORSHIP.totalLines);
    expect(segs[segs.length - 1].id).toBe("people");
  });

  it("folds agents beyond the validated slots into one segment", () => {
    const many = {
      ...SAMPLE_AI_AUTHORSHIP,
      agents: [...SAMPLE_AI_AUTHORSHIP.agents, { name: "A", lines: 10 }, { name: "B", lines: 5 }],
    };
    const segs = agentSegments(many);
    expect(segs.filter((s) => s.id !== "people" && s.id !== "other-agents")).toHaveLength(4);
    expect(segs.find((s) => s.id === "other-agents")?.value).toBe(15);
  });
});

describe("ownership matrix", () => {
  const { columns, rows } = ownershipMatrix(SAMPLE_OWNERSHIP);

  it("lists people before agents, one column per author", () => {
    const kinds = columns.map((c) => c.kind);
    expect(kinds).toEqual([...kinds].sort((a) => (a === "person" ? -1 : 1)));
    expect(new Set(columns.map((c) => c.id)).size).toBe(columns.length);
    expect(columns.map((c) => c.label)).toContain("Pi Coding Agent");
  });

  it("keeps every area's shares at 100%", () => {
    for (const row of rows) {
      expect(Object.values(row.values).reduce((n, v) => n + v, 0)).toBe(100);
    }
  });
});
