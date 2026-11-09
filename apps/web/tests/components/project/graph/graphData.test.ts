import { describe, expect, it } from "vitest";
import { toGraphData } from "@/components/project/graph/useGraphData";

describe("toGraphData", () => {
  it("gives each node its display type and keeps the rest of the node", () => {
    const data = toGraphData({
      nodes: [
        { id: "a.py", label: "a.py", kind: "file", file_path: "a.py", public_id: "file::a.py" },
        { id: "a.py::A", label: "A", kind: "class", file_path: "a.py", public_id: "a.py::A" },
        { id: "a.py::A.f", label: "f", kind: "method", file_path: "a.py", public_id: "a.py::A.f" },
        { id: "a.py::g", label: "g", kind: "function", file_path: "a.py", public_id: "a.py::g" },
      ],
      edges: [],
    });
    expect(data.nodes.map((n) => n.type)).toEqual(["File", "Class", "Method", "Function"]);
    expect(data.nodes[1]).toEqual({
      id: "a.py::A",
      label: "A",
      type: "Class",
      file_path: "a.py",
      public_id: "a.py::A",
    });
  });

  it("numbers edges in order so each has a stable id", () => {
    const data = toGraphData({
      nodes: [],
      edges: [
        { source: "a.py", target: "a.py::A", type: "CONTAINS" },
        { source: "a.py::A.f", target: "a.py::g", type: "CALLS" },
      ],
    });
    expect(data.edges).toEqual([
      { id: "e0", source: "a.py", target: "a.py::A", type: "CONTAINS" },
      { id: "e1", source: "a.py::A.f", target: "a.py::g", type: "CALLS" },
    ]);
  });
});
