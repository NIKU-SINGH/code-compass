import { describe, expect, it } from "vitest";
import { labelTextFor } from "@/components/project/graph/globeShading";

describe("labelTextFor", () => {
  it("adds the parent folder to file names", () => {
    const file = { type: "File" as const, label: "__init__.py", publicId: "file::src/billing/__init__.py" };
    expect(labelTextFor(file)).toBe("billing/__init__.py");
  });

  it("keeps a top-level file as is, and leaves other kinds alone", () => {
    expect(labelTextFor({ type: "File", label: "setup.py", publicId: "file::setup.py" })).toBe("setup.py");
    expect(labelTextFor({ type: "Class", label: "Invoice", publicId: "a.py::Invoice" })).toBe("Invoice");
  });
});
