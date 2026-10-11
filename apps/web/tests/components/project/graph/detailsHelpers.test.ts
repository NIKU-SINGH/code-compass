import { describe, expect, it } from "vitest";
import type { NodeDetail, SymbolRef } from "@/lib/api";
import { sectionsFor } from "@/components/project/graph/details/relatedSections";
import { displayName, locationLabel } from "@/components/project/graph/details/symbolLabel";

const sym = (id: string, kind: SymbolRef["kind"], name: string): SymbolRef => ({
  id,
  kind,
  name,
  qualified_name: name,
  file_path: "a.py",
  line_start: 1,
  line_end: 2,
  signature: null,
});

describe("displayName", () => {
  it("uses the Class.member tail for definitions and the name for files", () => {
    expect(displayName(sym("app/auth.py::Policy.allows", "method", "allows"))).toBe("Policy.allows");
    expect(displayName(sym("file::app/auth.py", "file", "auth.py"))).toBe("auth.py");
    expect(displayName(sym("ext::json.dumps", "external", "dumps"))).toBe("dumps");
  });
});

describe("locationLabel", () => {
  it("adapts to what location is known", () => {
    expect(locationLabel("a.py", 18, 40)).toBe("a.py:18-40");
    expect(locationLabel("a.py", 7, 7)).toBe("a.py:7");
    expect(locationLabel("a.py", 7, null)).toBe("a.py:7");
    expect(locationLabel("a.py", null, null)).toBe("a.py");
    expect(locationLabel(null, null, null)).toBe("");
  });
});

describe("sectionsFor", () => {
  const detailOf = (kind: SymbolRef["kind"]) =>
    ({
      symbol: sym("x", kind, "x"),
      bases: [],
      subclasses: [],
      members: [],
      callees: [],
      callers: [],
      imports: [],
      imported_by: [],
    }) as unknown as NodeDetail;

  it("shows the relationships that fit each kind", () => {
    const titles = (k: SymbolRef["kind"]) => sectionsFor(detailOf(k)).map((s) => s.title);
    expect(titles("class")).toEqual(["Base classes", "Subclasses", "Methods"]);
    expect(titles("method")).toEqual(["Calls", "Called by"]);
    expect(titles("function")).toEqual(["Calls", "Called by"]);
    expect(titles("file")).toEqual(["Defines", "Imports", "Imported by"]);
    expect(titles("external")).toEqual([]);
  });
});
