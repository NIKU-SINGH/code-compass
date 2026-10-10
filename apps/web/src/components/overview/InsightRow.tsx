import { KIND_STYLES } from "@/components/impact/symbolKind";
import { cn } from "@/lib/utils";
import type { InsightRowData } from "./insightCards";

interface InsightRowProps {
  row: InsightRowData;
  /** When provided the row is a button; otherwise it is static. */
  onSelect?: (row: InsightRowData) => void;
}

export function InsightRow({ row, onSelect }: InsightRowProps) {
  const kind = KIND_STYLES[row.kind];
  const Icon = kind.icon;
  const content = (
    <>
      <span className="flex min-w-0 items-center gap-2.5">
        <Icon className={cn("size-3.5 flex-none", kind.textClass)} aria-hidden />
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-mono text-xs">{row.name}</span>
          {row.location && <span className="truncate font-mono text-[11px] text-muted-foreground">{row.location}</span>}
        </span>
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
        <span className="block h-full rounded-full bg-primary" style={{ width: `${row.barPercent}%` }} />
      </span>
      <span className="whitespace-nowrap text-right font-mono text-xs text-muted-foreground">{row.metric}</span>
    </>
  );
  const layout = "grid min-h-10 w-full grid-cols-[minmax(0,1fr)_5rem_6.5rem] items-center gap-3 px-3.5 py-1 text-left";
  if (!onSelect) return <div className={layout}>{content}</div>;
  return (
    <button
      type="button"
      onClick={() => onSelect(row)}
      className={cn(layout, "cursor-pointer hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring")}
    >
      {content}
    </button>
  );
}
