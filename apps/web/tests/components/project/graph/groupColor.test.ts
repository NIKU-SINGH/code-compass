import { describe, expect, it } from "vitest";
import { folderOf, paletteIndexFor } from "@/components/project/graph/groupColor";

describe("folderOf", () => {
  it("handles file and symbol public ids", () => {
    expect(folderOf("file::src/billing/invoice.py")).toBe("src/billing");
    expect(folderOf("src/billing/invoice.py::Invoice.total")).toBe("src/billing");
    expect(folderOf("file::setup.py")).toBe("");
  });
});

describe("paletteIndexFor", () => {
  it("is stable and within the palette", () => {
    expect(paletteIndexFor("src/billing")).toBe(paletteIndexFor("src/billing"));
    for (const f of ["", "a", "src/billing", "tests/unit"]) {
      expect(paletteIndexFor(f)).toBeGreaterThanOrEqual(0);
      expect(paletteIndexFor(f)).toBeLessThan(5);
    }
  });

  it("spreads different folders over more than one colour", () => {
    const slots = new Set(["a", "b", "c", "d", "e", "f", "g"].map((f) => paletteIndexFor(f)));
    expect(slots.size).toBeGreaterThan(1);
  });
});
