import { describe, expect, it } from "vitest";
import { parseDocstring } from "@/components/project/graph/details/parseDocstring";

const WRITE_CONTAINS = `Write structural containment edges (CONTAINS) for a file.

    Establishes relationships between a file and its defined classes/functions,
    as well as between classes and their methods. Calls \`\`on_edge\`\` once per
    edge successfully written, enabling granular progress reporting.

    Args:
        db: Active database connection.
        f: The \`ParsedFile\` whose internal structure is being
            persisted.
        on_edge: Callback invoked once for each edge successfully written.

    Returns:
        Number of edges written.

    Raises:
        PersistenceError: If a write fails.
`;

describe("parseDocstring", () => {
  const doc = parseDocstring(WRITE_CONTAINS);

  it("separates the summary from the body, re-flowing hard-wrapped lines", () => {
    expect(doc.summary).toBe("Write structural containment edges (CONTAINS) for a file.");
    expect(doc.body).toEqual([
      "Establishes relationships between a file and its defined classes/functions, as well as between classes and their methods. Calls ``on_edge`` once per edge successfully written, enabling granular progress reporting.",
    ]);
  });

  it("turns Args into entries and joins an entry's continuation lines", () => {
    const params = doc.sections.find((s) => s.title === "Parameters");
    expect(params?.kind).toBe("entries");
    if (params?.kind !== "entries") return;
    expect(params.entries.map((e) => e.name)).toEqual(["db", "f", "on_edge"]);
    expect(params.entries[1].text).toBe("The `ParsedFile` whose internal structure is being persisted.");
  });

  it("keeps Returns as text and Raises as named entries, in order", () => {
    expect(doc.sections.map((s) => s.title)).toEqual(["Parameters", "Returns", "Raises"]);
    const returns = doc.sections[1];
    expect(returns).toMatchObject({ kind: "text", paragraphs: ["Number of edges written."] });
    const raises = doc.sections[2];
    expect(raises.kind === "entries" && raises.entries[0]).toMatchObject({
      name: "PersistenceError",
      text: "If a write fails.",
    });
  });

  it("reads a parameter's type from parentheses", () => {
    const d = parseDocstring("Do it.\n\nArgs:\n    size (int): The size.\n");
    const s = d.sections[0];
    expect(s.kind === "entries" && s.entries[0]).toMatchObject({ name: "size", type: "int", text: "The size." });
  });

  it("handles a plain one-line docstring and an empty one", () => {
    expect(parseDocstring("Format a byte count.")).toEqual({ summary: "Format a byte count.", body: [], sections: [] });
    expect(parseDocstring("")).toEqual({ summary: "", body: [], sections: [] });
  });

  it("keeps bullet lists as lines and Example blocks as code", () => {
    const d = parseDocstring("Summary.\n\nSteps:\n- one\n- two\n\nExample:\n    run(1)\n    run(2)\n");
    expect(d.body).toEqual(["Steps:\n- one\n- two"]);
    expect(d.sections[0]).toEqual({ kind: "code", title: "Example", code: "run(1)\nrun(2)" });
  });
});
