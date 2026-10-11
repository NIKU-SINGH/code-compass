import type { NodeDetail, SymbolRef } from "@/lib/api";

export interface RelatedSection {
  title: string;
  items: ReadonlyArray<SymbolRef>;
  emptyText: string;
}

/** The relationship lists worth showing for a node of this kind, in display order. */
export function sectionsFor(detail: NodeDetail): RelatedSection[] {
  switch (detail.symbol.kind) {
    case "class":
      return [
        {
          title: "Base classes",
          items: detail.bases,
          emptyText: "No base classes in this repository.",
        },
        { title: "Subclasses", items: detail.subclasses, emptyText: "No subclasses." },
        { title: "Methods", items: detail.members, emptyText: "No methods." },
      ];
    case "function":
    case "method":
      return [
        { title: "Calls", items: detail.callees, emptyText: "Calls nothing in this repository." },
        { title: "Called by", items: detail.callers, emptyText: "Not called from this repository." },
      ];
    case "file":
      return [
        { title: "Defines", items: detail.members, emptyText: "Defines no classes or functions." },
        { title: "Imports", items: detail.imports, emptyText: "Imports no repository files." },
        { title: "Imported by", items: detail.imported_by, emptyText: "Not imported anywhere." },
      ];
    default:
      return [];
  }
}
