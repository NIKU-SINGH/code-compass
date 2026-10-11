import { dedent } from "./meta";

export interface DocEntry {
  name: string;
  type: string | null;
  text: string;
}

export type DocSection =
  | { kind: "entries"; title: string; entries: ReadonlyArray<DocEntry> }
  | { kind: "text"; title: string; paragraphs: ReadonlyArray<string> }
  | { kind: "code"; title: string; code: string };

export interface ParsedDoc {
  /** First paragraph: the one-line summary. */
  summary: string;
  /** Remaining paragraphs before the first section, re-flowed. */
  body: ReadonlyArray<string>;
  sections: ReadonlyArray<DocSection>;
}

const SECTION_HEADER = /^(Args|Arguments|Parameters|Attributes|Returns?|Yields?|Raises|Examples?|Notes?|Warnings?|See Also):\s*$/;
const TITLES: Record<string, string> = {
  args: "Parameters",
  arguments: "Parameters",
  parameters: "Parameters",
  attributes: "Attributes",
  return: "Returns",
  returns: "Returns",
  yield: "Yields",
  yields: "Yields",
  raises: "Raises",
  example: "Example",
  examples: "Example",
  note: "Note",
  notes: "Note",
  warning: "Warning",
  warnings: "Warning",
  "see also": "See also",
};
const ENTRY_SECTIONS = new Set(["Parameters", "Attributes", "Raises"]);
const ENTRY = /^([\w.*]+)\s*(?:\(([^)]*)\))?\s*:\s*(.*)$/;
const LIST_ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/;

const indentOf = (line: string) => line.length - line.trimStart().length;

/**
 * Paragraphs from lines: blank lines separate them, and hard-wrapped lines are joined into one
 * flowing line, except in a list, whose line breaks are kept.
 */
function toParagraphs(lines: ReadonlyArray<string>): string[] {
  const out: string[] = [];
  let group: string[] = [];
  const flush = () => {
    if (group.length === 0) return;
    const trimmed = group.map((l) => l.trim());
    out.push(group.some((l) => LIST_ITEM.test(l)) ? trimmed.join("\n") : trimmed.join(" "));
    group = [];
  };
  for (const line of lines) {
    if (line.trim() === "") flush();
    else group.push(line);
  }
  flush();
  return out;
}

function parseEntries(lines: ReadonlyArray<string>): DocEntry[] {
  const filled = lines.filter((l) => l.trim() !== "");
  if (filled.length === 0) return [];
  const base = Math.min(...filled.map(indentOf));
  const entries: DocEntry[] = [];
  for (const line of filled) {
    const match = indentOf(line) === base ? ENTRY.exec(line.trim()) : null;
    if (match) {
      entries.push({ name: match[1], type: match[2] ?? null, text: match[3].trim() });
    } else if (entries.length > 0) {
      const last = entries[entries.length - 1];
      last.text = `${last.text} ${line.trim()}`.trim();
    }
  }
  return entries;
}

function toSection(title: string, lines: ReadonlyArray<string>): DocSection | null {
  const body = dedent(lines.join("\n"));
  if (body.trim() === "") return null;
  if (title === "Example") return { kind: "code", title, code: body };
  if (ENTRY_SECTIONS.has(title)) {
    const entries = parseEntries(body.split("\n"));
    if (entries.length > 0) return { kind: "entries", title, entries };
  }
  return { kind: "text", title, paragraphs: toParagraphs(body.split("\n")) };
}

/**
 * Splits a Google-style docstring into a summary, body paragraphs and its `Args:` / `Returns:` /
 * `Raises:` style sections, so it can be laid out instead of printed as raw text. A docstring in
 * some other style simply comes back as a summary and paragraphs.
 */
export function parseDocstring(raw: string): ParsedDoc {
  const head: string[] = [];
  const blocks: { title: string; lines: string[] }[] = [];
  let current = head;
  for (const line of dedent(raw).split("\n")) {
    const header = SECTION_HEADER.exec(line);
    if (header) {
      const block = { title: TITLES[header[1].toLowerCase()] ?? header[1], lines: [] as string[] };
      blocks.push(block);
      current = block.lines;
    } else {
      current.push(line);
    }
  }
  const paragraphs = toParagraphs(head);
  return {
    summary: paragraphs[0] ?? "",
    body: paragraphs.slice(1),
    sections: blocks.flatMap((b) => toSection(b.title, b.lines) ?? []),
  };
}
