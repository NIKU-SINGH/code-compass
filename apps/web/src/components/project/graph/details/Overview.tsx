"use client";

import type { SymbolRef } from "@/lib/api";
import type { RelatedSection } from "./relatedSections";
import { Docstring } from "./Docstring";
import { compactName, type MetaChip } from "./meta";
import { iconForKind, locationLabel } from "./symbolLabel";

interface Props {
  sections: ReadonlyArray<RelatedSection>;
  /** Whether the item exists in the graph and can be selected. */
  canSelect: (symbol: SymbolRef) => boolean;
  onSelect: (symbol: SymbolRef) => void;
  /** True when some lists were cut at the backend's per-list limit. */
  truncated: boolean;
  /** What the node is, ahead of what it connects to; classes and functions only. */
  about?: { docstring: string | null; chips: ReadonlyArray<MetaChip> };
}

const HEADING = "text-[10px] font-semibold uppercase tracking-wider text-muted-foreground";

/**
 * Everything the node connects to, one titled list per relationship, each shown in full. Empty
 * relationships are left out.
 */
export function Overview({ sections, canSelect, onSelect, truncated, about }: Props) {
  const filled = sections.filter((s) => s.items.length > 0);
  const hasAbout = Boolean(about && (about.docstring || about.chips.length > 0));
  if (filled.length === 0 && !hasAbout) {
    return <p className="px-4 py-3 text-muted-foreground">No related symbols in this repository.</p>;
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-3">
      {about?.docstring && (
        <section aria-label="Description" className="flex flex-col gap-1.5">
          <h3 className={HEADING}>Description</h3>
          <Docstring text={about.docstring} />
        </section>
      )}
      {about && about.chips.length > 0 && (
        <section aria-label="Location" className="flex flex-col gap-1.5">
          <h3 className={HEADING}>Location</h3>
          <ul className="flex flex-wrap gap-1.5">
            {about.chips.map((chip) => (
              <li key={chip.label} className="flex gap-1 rounded-md bg-muted/50 px-2 py-1">
                <span className="text-muted-foreground">{chip.label}</span>
                <span className="font-mono">{chip.value}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {filled.map((s) => (
        <section key={s.title} aria-label={s.title} className="flex flex-col gap-1">
          <h3 className={HEADING}>
            {s.title} <span className="ml-1 font-mono">{s.items.length}</span>
          </h3>
          <ul className="-mx-2 flex flex-col">
            {s.items.map((symbol) => {
              const Icon = iconForKind(symbol.kind);
              return (
                <li key={symbol.id}>
                  <button
                    type="button"
                    disabled={!canSelect(symbol)}
                    onClick={() => onSelect(symbol)}
                    title={locationLabel(symbol.file_path, symbol.line_start, symbol.line_end)}
                    className="flex w-full items-center gap-2 rounded px-2 py-1 text-left enabled:cursor-pointer enabled:hover:bg-muted disabled:opacity-60"
                  >
                    <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="min-w-0 flex-1 truncate font-mono text-foreground">{compactName(symbol)}</span>
                    {symbol.kind !== "file" && symbol.line_start !== null && (
                      <span className="font-mono text-[10px] text-muted-foreground">:{symbol.line_start}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {truncated && <p className="text-muted-foreground">Some lists are cut short.</p>}
    </div>
  );
}
