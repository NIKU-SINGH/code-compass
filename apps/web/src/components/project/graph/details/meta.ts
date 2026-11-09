import type { NodeDetail, SymbolRef } from "@/lib/api";

/**
 * Path trimmed to its last `keep` segments, with `…/` where it was cut: the full path is in the
 * tooltip and the copy button, so the panel only needs enough to recognise the file.
 */
export function shortPath(path: string, keep = 3): string {
  const parts = path.split("/").filter(Boolean);
  return parts.length <= keep ? path : `…/${parts.slice(-keep).join("/")}`;
}

/** A file reads best as `folder/name.py`; anything else as its `Class.member` name. */
export function compactName(symbol: Pick<SymbolRef, "id" | "name" | "kind" | "file_path">): string {
  if (symbol.kind === "file") {
    const parts = (symbol.file_path ?? symbol.name).split("/").filter(Boolean);
    return parts.slice(-2).join("/");
  }
  if (symbol.kind === "external") return symbol.name;
  return symbol.id.split("::").pop() || symbol.name;
}

/**
 * Docstring text without the indentation Python source gives it: leading and trailing blank lines
 * go, and the indentation shared by every line after the first is removed.
 */
export function dedent(text: string): string {
  const lines = text.replace(/\s+$/, "").replace(/^\s*\n/, "").split("\n");
  const indents = lines
    .slice(1)
    .filter((l) => l.trim() !== "")
    .map((l) => l.length - l.trimStart().length);
  const cut = indents.length > 0 ? Math.min(...indents) : 0;
  return lines.map((l, i) => (i === 0 ? l.trimStart() : l.slice(Math.min(cut, l.length - l.trimStart().length)))).join("\n");
}

export interface MetaChip {
  label: string;
  value: string;
}

/**
 * The few facts worth a glance for a node: where it sits and how big it is. Relationship counts
 * are left to the tabs, which already show them.
 */
export function metaChips(detail: NodeDetail): MetaChip[] {
  const { line_start: start, line_end: end } = detail.symbol;
  if (start === null) return [];
  const chips: MetaChip[] = [
    { label: "Lines", value: end !== null && end !== start ? `${start}–${end}` : String(start) },
  ];
  if (end !== null && end >= start) {
    const size = end - start + 1;
    chips.push({ label: "Size", value: `${size} line${size === 1 ? "" : "s"}` });
  }
  return chips;
}
