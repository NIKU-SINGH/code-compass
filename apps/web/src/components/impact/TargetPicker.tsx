"use client";

import { Search } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { SearchHit, SymbolRef } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KIND_STYLES, symbolLocation } from "./symbolKind";

interface TargetPickerProps {
  query: string;
  onQueryChange: (query: string) => void;
  results: ReadonlyArray<SearchHit>;
  loading: boolean;
  onPick: (symbol: SymbolRef) => void;
  autoFocus?: boolean;
}

export function TargetPicker({ query, onQueryChange, results, loading, onPick, autoFocus }: TargetPickerProps) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const showList = open && query.trim().length > 0;
  const activeIndex = Math.min(active, Math.max(results.length - 1, 0));

  const pick = (hit: SearchHit) => {
    setOpen(false);
    onPick(hit.symbol);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive(Math.min(activeIndex + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(Math.max(activeIndex - 1, 0));
    } else if (e.key === "Enter" && showList && results[activeIndex]) {
      e.preventDefault();
      pick(results[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative" role="search">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <Input
        role="combobox"
        aria-label="Search a function, class or file"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && results[activeIndex] ? `${listId}-${activeIndex}` : undefined}
        autoFocus={autoFocus}
        autoComplete="off"
        placeholder="Search a function, class or file…"
        className="pl-9"
        value={query}
        onChange={(e) => {
          onQueryChange(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <div className="absolute inset-x-0 top-full z-20 mt-1 rounded-md border border-border bg-popover text-popover-foreground shadow-md">
          <ScrollArea className="max-h-72">
            <ul id={listId} role="listbox" aria-label="Matching symbols" className="p-1">
              {results.map((hit, i) => {
                const kind = KIND_STYLES[hit.symbol.kind];
                const Icon = kind.icon;
                return (
                  <li
                    key={hit.symbol.id}
                    id={`${listId}-${i}`}
                    role="option"
                    aria-selected={i === activeIndex}
                    // mousedown fires before the input's blur closes the list
                    onMouseDown={(e) => {
                      e.preventDefault();
                      pick(hit);
                    }}
                    onMouseEnter={() => setActive(i)}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-sm px-2.5 py-1.5",
                      i === activeIndex && "bg-muted",
                    )}
                  >
                    <Icon className={cn("size-3.5 flex-none", kind.textClass)} aria-hidden />
                    <span className="font-mono text-[13px]">{hit.symbol.name}</span>
                    <span className="flex-1 truncate font-mono text-xs text-muted-foreground">
                      {symbolLocation(hit.symbol)}
                    </span>
                    <Badge variant="secondary" className={cn("text-[10px]", kind.textClass)}>
                      {kind.label}
                    </Badge>
                  </li>
                );
              })}
            </ul>
            {results.length === 0 && (
              <p className="px-3 py-2 text-xs text-muted-foreground" role="status">
                {loading ? "Searching…" : "No matches"}
              </p>
            )}
          </ScrollArea>
        </div>
      )}
    </div>
  );
}
