"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { SearchHit, SymbolRef } from "@/lib/api";
import { compactName, shortPath } from "@/components/project/graph/details/meta";
import { iconForKind } from "@/components/project/graph/details/symbolLabel";
import { useSymbolSearch } from "./useSymbolSearch";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the chosen symbol; the palette closes itself first. */
  onSelect: (symbol: SymbolRef) => void;
}

const GROUPS: ReadonlyArray<{ title: string; kinds: ReadonlyArray<SymbolRef["kind"]> }> = [
  { title: "Files", kinds: ["file"] },
  { title: "Classes", kinds: ["class"] },
  { title: "Functions", kinds: ["function", "method"] },
];

function hitsOf(hits: ReadonlyArray<SearchHit>, kinds: ReadonlyArray<SymbolRef["kind"]>) {
  return hits.filter((h) => kinds.includes(h.symbol.kind));
}

/** Command palette over the symbol search: type, arrow to a result, Enter to open it in the graph. */
export function SearchPalette({ open, onOpenChange, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const { hits, loading, error } = useSymbolSearch(open ? query : "");

  const choose = (symbol: SymbolRef) => {
    onOpenChange(false);
    setQuery("");
    onSelect(symbol);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setQuery("");
        onOpenChange(next);
      }}
    >
      <DialogContent className="top-[20%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl [&>button]:hidden">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <DialogDescription className="sr-only">Search files, classes and functions</DialogDescription>
        {/* The server already filtered; cmdk must not filter again. */}
        <Command shouldFilter={false} className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground">
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder="Search files, classes, functions…"
            autoFocus
          />
          <CommandList className="max-h-80">
            {query.trim() === "" && (
              <p className="px-4 py-6 text-center text-xs text-muted-foreground">
                Type a name or path to find it in the graph.
              </p>
            )}
            {query.trim() !== "" && !loading && !error && hits.length === 0 && (
              <CommandEmpty>No matches.</CommandEmpty>
            )}
            {error && <p className="px-4 py-6 text-center text-xs text-muted-foreground">Search is unavailable right now.</p>}
            {GROUPS.map(({ title, kinds }) => {
              const group = hitsOf(hits, kinds);
              if (group.length === 0) return null;
              return (
                <CommandGroup key={title} heading={title}>
                  {group.map(({ symbol }) => {
                    const Icon = iconForKind(symbol.kind);
                    return (
                      <CommandItem
                        key={symbol.id}
                        value={symbol.id}
                        onSelect={() => choose(symbol)}
                        className="cursor-pointer gap-2 py-2"
                      >
                        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                        <span className="min-w-0 truncate font-mono text-xs">{compactName(symbol)}</span>
                        <span className="ml-auto min-w-0 truncate font-mono text-[10px] text-muted-foreground">
                          {symbol.file_path ? shortPath(symbol.file_path, 2) : ""}
                        </span>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              );
            })}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
