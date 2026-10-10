import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { BreakdownSegment } from "./insightCards";

interface BreakdownBarProps {
  title: string;
  segments: ReadonlyArray<BreakdownSegment>;
  className?: string;
}

/** Proportional segmented bar with a legend; used for entity kinds and edge types. */
export function BreakdownBar({ title, segments, className }: BreakdownBarProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  return (
    <Card className={cn("flex flex-col gap-3 px-4 py-3.5 shadow-none", className)}>
      <div className="flex items-baseline gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-muted-foreground tabular-nums">{total.toLocaleString()} total</span>
      </div>
      <div
        role="img"
        aria-label={segments.map((s) => `${s.label} ${s.value}`).join(", ")}
        className="flex h-2.5 gap-0.5 overflow-hidden rounded-sm bg-muted"
      >
        {segments
          .filter((s) => s.value > 0)
          .map((s) => (
            <span key={s.id} title={`${s.label} · ${s.value}`} className={cn("h-full", s.colorClass)} style={{ flexGrow: s.value, flexBasis: 0 }} />
          ))}
      </div>
      <ul className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
        {segments.map((s) => (
          <li key={s.id} className="flex items-center gap-2">
            <span className={cn("size-2 flex-none rounded-full", s.colorClass)} aria-hidden />
            <span className="flex-1 truncate text-muted-foreground">{s.label}</span>
            <span className="font-mono tabular-nums">{s.value.toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
