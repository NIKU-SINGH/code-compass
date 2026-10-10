import { CircleCheck, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { SymbolRef } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KIND_STYLES, symbolLocation } from "./symbolKind";

export function EmptyResult() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-5 py-11 text-center">
      <CircleCheck className="size-6 text-success" aria-hidden />
      <div className="font-medium">Nothing depends on this</div>
      <div className="max-w-sm text-xs text-muted-foreground">
        This only reflects resolved calls and imports. Tests and entry points often look like this.
      </div>
    </div>
  );
}

export function IdleHint() {
  return <p className="text-sm text-muted-foreground">Pick a function, class or file to see what it affects.</p>;
}

export function LoadingRows() {
  return (
    <div role="status" aria-label="Loading impact analysis" className="flex flex-col gap-3">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  );
}

interface SymbolChoiceListProps {
  symbols: ReadonlyArray<SymbolRef>;
  onChoose: (symbol: SymbolRef) => void;
}

function SymbolChoiceList({ symbols, onChoose }: SymbolChoiceListProps) {
  return (
    <ul className="flex flex-col gap-px overflow-hidden rounded-lg border border-border bg-border">
      {symbols.map((s) => {
        const kind = KIND_STYLES[s.kind];
        const Icon = kind.icon;
        return (
          <li key={s.id}>
            <button
              type="button"
              onClick={() => onChoose(s)}
              className="flex w-full cursor-pointer items-center gap-3 bg-card px-3.5 py-2 text-left hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon className={cn("size-3.5 flex-none", kind.textClass)} aria-hidden />
              <span className="font-mono text-[13px]">{s.name}</span>
              <span className="truncate font-mono text-xs text-muted-foreground">{symbolLocation(s)}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

interface AmbiguousChooserProps {
  reference: string;
  candidates: ReadonlyArray<SymbolRef>;
  onChoose: (symbol: SymbolRef) => void;
}

export function AmbiguousChooser({ reference, candidates, onChoose }: AmbiguousChooserProps) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">
        <span className="font-mono">{reference}</span> matches more than one symbol. Which did you mean?
      </p>
      <SymbolChoiceList symbols={candidates} onChoose={onChoose} />
    </div>
  );
}

interface NotFoundHintProps {
  reference: string;
  suggestions: ReadonlyArray<SymbolRef>;
  onChoose: (symbol: SymbolRef) => void;
}

export function NotFoundHint({ reference, suggestions, onChoose }: NotFoundHintProps) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">No symbol matches &apos;{reference}&apos;</p>
      {suggestions.length > 0 && (
        <>
          <p className="text-xs text-muted-foreground">Did you mean:</p>
          <SymbolChoiceList symbols={suggestions} onChoose={onChoose} />
        </>
      )}
    </div>
  );
}

export function RetryButton({ onRetry }: { onRetry: () => void }) {
  return (
    <Button variant="outline" size="sm" className="cursor-pointer" onClick={onRetry}>
      <RefreshCw className="size-3.5" aria-hidden />
      Retry
    </Button>
  );
}
