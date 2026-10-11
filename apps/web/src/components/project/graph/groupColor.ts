import { resolveCssColor } from "@/lib/cssColor";

// Existing node-kind tokens reused as a categorical palette, so no new colours enter the theme.
const PALETTE_TOKENS = [
  "--kind-file",
  "--kind-class",
  "--kind-function",
  "--kind-method",
  "--kind-external",
];

/**
 * Folder a stored public id lives in: `file::src/billing/invoice.py` and
 * `src/billing/invoice.py::Invoice.total` both give `src/billing`.
 */
export function folderOf(publicId: string): string {
  const path = publicId.startsWith("file::") ? publicId.slice("file::".length) : publicId.split("::")[0];
  const slash = path.lastIndexOf("/");
  return slash === -1 ? "" : path.slice(0, slash);
}

/** Stable palette slot for a folder, so a folder keeps its colour across reloads and expands. */
export function paletteIndexFor(folder: string, size = PALETTE_TOKENS.length): number {
  let h = 5381;
  for (let i = 0; i < folder.length; i++) h = ((h << 5) + h + folder.charCodeAt(i)) >>> 0;
  return h % size;
}

/** `#rrggbb` for the folder's group colour in the active scheme. */
export function colorForFolder(folder: string): string {
  return resolveCssColor(PALETTE_TOKENS[paletteIndexFor(folder)]);
}
