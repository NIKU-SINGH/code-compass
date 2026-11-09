import type { ResultItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KIND_STYLES, symbolLocation } from "./symbolKind";
import { viaText } from "./viaText";

interface AffectedRowProps {
  item: ResultItem;
  onRetarget: (id: string) => void;
}

function confidenceClass(c: number | null): string {
  if (c === null) return "text-muted-foreground";
  return c >= 1.0 ? "text-success" : "text-warning";
}

/** Text and tooltip of the last column: a call confidence, or what kind of link this is. */
function confidenceCell(item: ResultItem): { text: string; title: string } {
  const c = item.min_confidence;
  if (c !== null) return { text: c.toFixed(2), title: `Minimum edge confidence ${c.toFixed(2)}` };
  const kind = item.via?.kind;
  if (kind === "IMPORTS") {
    return { text: "import", title: "Import dependency (not a call)" };
  }
  return { text: "—", title: "Confidence unknown" };
}

export function AffectedRow({ item, onRetarget }: AffectedRowProps) {
  const { symbol } = item;
  const kind = KIND_STYLES[symbol.kind];
  const Icon = kind.icon;
  const confidence = item.min_confidence;
  const cell = confidenceCell(item);
  return (
    <button
      type="button"
      onClick={() => onRetarget(symbol.id)}
      title={`Re-target impact on ${symbol.name}`}
      className="grid min-h-9 w-full cursor-pointer grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_3rem] items-center gap-3 bg-card px-3.5 text-left hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex min-w-0 items-center gap-2">
        <Icon className={cn("size-3.5 flex-none", kind.textClass)} aria-hidden />
        <span className="truncate font-mono text-[13px]">{symbol.name}</span>
      </span>
      <span className="truncate font-mono text-xs text-muted-foreground">{symbolLocation(symbol)}</span>
      <span className="truncate text-xs italic text-muted-foreground">{viaText(item.via)}</span>
      <span className={cn("text-right font-mono text-xs", confidenceClass(confidence))} title={cell.title}>
        {cell.text}
      </span>
    </button>
  );
}
