import { Box, Braces, FileText, Package, Puzzle, type LucideIcon } from "lucide-react";
import type { SymbolKind, SymbolRef } from "@/lib/api";

interface KindStyle {
  icon: LucideIcon;
  /** Tailwind text colour class from the `--kind-*` theme tokens. */
  textClass: string;
  /** Tailwind background tint class from the same token. */
  tintClass: string;
  label: string;
}

export const KIND_STYLES: Record<SymbolKind, KindStyle> = {
  file: { icon: FileText, textClass: "text-kind-file", tintClass: "bg-kind-file/15", label: "File" },
  class: { icon: Box, textClass: "text-kind-class", tintClass: "bg-kind-class/15", label: "Class" },
  function: { icon: Braces, textClass: "text-kind-function", tintClass: "bg-kind-function/15", label: "Function" },
  method: { icon: Puzzle, textClass: "text-kind-method", tintClass: "bg-kind-method/15", label: "Method" },
  external: { icon: Package, textClass: "text-kind-external", tintClass: "bg-kind-external/15", label: "External" },
};

/** `path:line` (line numbers from the API are already 1-indexed), or `path`, or empty. */
export function symbolLocation(s: Pick<SymbolRef, "file_path" | "line_start">): string {
  if (s.file_path === null) return "";
  return s.line_start === null ? s.file_path : `${s.file_path}:${s.line_start}`;
}
