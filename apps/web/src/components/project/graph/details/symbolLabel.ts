import { Box, Braces, FileCode2, Package, type LucideIcon } from "lucide-react";
import type { SymbolRef } from "@/lib/api";

/**
 * Short name for a symbol in a list: `Policy.allows` for a method, `permissions.py` for a file.
 * Public ids end in `::<[Class.]name>`, which is exactly that.
 */
export function displayName(symbol: Pick<SymbolRef, "id" | "name" | "kind">): string {
  if (symbol.kind === "file" || symbol.kind === "external") return symbol.name;
  return symbol.id.split("::").pop() || symbol.name;
}

/** `path:start-end`, `path:line` or just `path`, whichever the symbol's location allows. */
export function locationLabel(
  path: string | null,
  start: number | null,
  end: number | null,
): string {
  if (!path) return "";
  if (start === null) return path;
  return end === null || end === start ? `${path}:${start}` : `${path}:${start}-${end}`;
}

/** Icon for a symbol kind; accepts the API's lower-case kinds and the graph's node types. */
export function iconForKind(kind: string): LucideIcon {
  const k = kind.toLowerCase();
  if (k === "file") return FileCode2;
  if (k === "class") return Box;
  if (k.startsWith("external")) return Package;
  return Braces;
}
