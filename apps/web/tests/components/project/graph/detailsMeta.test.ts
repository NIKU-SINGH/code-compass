import { describe, expect, it } from "vitest";
import type { NodeDetail } from "@/lib/api";
import { compactName, dedent, metaChips, shortPath } from "@/components/project/graph/details/meta";

describe("shortPath", () => {
  it("keeps short paths whole and trims long ones from the front", () => {
    expect(shortPath("app/auth.py")).toBe("app/auth.py");
    expect(shortPath("a/b/c")).toBe("a/b/c");
    expect(shortPath("packages/core/src/compass_core/errors.py")).toBe("…/src/compass_core/errors.py");
    expect(shortPath("a/b/c/d.py", 2)).toBe("…/c/d.py");
  });
});

describe("compactName", () => {
  const ref = (kind: "file" | "class" | "method" | "external", id: string, name: string, file_path: string | null) => ({
    id,
    kind,
    name,
    file_path,
  });

  it("shows files as folder/name and definitions by their qualified tail", () => {
    expect(compactName(ref("file", "file::packages/core/graph/db.py", "db.py", "packages/core/graph/db.py"))).toBe("graph/db.py");
    expect(compactName(ref("file", "file::setup.py", "setup.py", "setup.py"))).toBe("setup.py");
    expect(compactName(ref("method", "app/auth.py::Policy.allows", "allows", "app/auth.py"))).toBe("Policy.allows");
    expect(compactName(ref("external", "ext::json.dumps", "dumps", null))).toBe("dumps");
  });
});

describe("metaChips", () => {
  const detail = (start: number | null, end: number | null) =>
    ({ symbol: { line_start: start, line_end: end } }) as unknown as NodeDetail;

  it("gives the line range and size of a definition", () => {
    expect(metaChips(detail(84, 190))).toEqual([
      { label: "Lines", value: "84–190" },
      { label: "Size", value: "107 lines" },
    ]);
  });

  it("handles a single line, and files (no lines) get no chips", () => {
    expect(metaChips(detail(7, 7))).toEqual([
      { label: "Lines", value: "7" },
      { label: "Size", value: "1 line" },
    ]);
    expect(metaChips(detail(null, null))).toEqual([]);
  });
});

describe("dedent", () => {
  it("removes the indentation Python gives a docstring and trims blank edges", () => {
    const doc = "Format a byte count.\n\n    Args:\n        size_bytes: The number.\n\n    Returns:\n        A string.\n    ";
    expect(dedent(doc)).toBe("Format a byte count.\n\nArgs:\n    size_bytes: The number.\n\nReturns:\n    A string.");
  });

  it("leaves a one-line docstring alone", () => {
    expect(dedent("Short.")).toBe("Short.");
    expect(dedent("  Short.  ")).toBe("Short.");
  });
});
