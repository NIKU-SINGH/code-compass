import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface CompositionSegment {
  id: string;
  label: string;
  value: number;
  /** Tailwind background class from the `--kind-*` tokens. */
  colorClass: string;
}

export interface CompositionEdge {
  id: string;
  label: string;
  value: number;
  /** Tailwind background class from the `--edge-*` tokens. */
  colorClass: string;
  /** 0-100, relative to the busiest edge type. */
  barPercent: number;
}

interface Props {
  nodeCount: number;
  edgeCount: number;
  segments: ReadonlyArray<CompositionSegment>;
  edges: ReadonlyArray<CompositionEdge>;
}

/** Node mix as one segmented bar with a counted legend, then each edge type with its own bar. */
export function GraphComposition({ nodeCount, edgeCount, segments, edges }: Props) {
  return (
    <Card className="flex min-w-0 flex-col gap-4 px-5 py-4 shadow-none">
      <div className="flex items-baseline gap-3">
        <h2 className="text-sm font-semibold">Graph composition</h2>
        <span className="text-xs text-muted-foreground tabular-nums">
          {nodeCount.toLocaleString()} nodes · {edgeCount.toLocaleString()} edges
        </span>
      </div>

      <div className="flex flex-col gap-2.5">
        <div
          role="img"
          aria-label={segments.map((s) => `${s.label} ${s.value}`).join(", ")}
          className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-muted"
        >
          {segments
            .filter((s) => s.value > 0)
            .map((s) => (
              <span key={s.id} title={`${s.label} · ${s.value}`} className={cn("h-full", s.colorClass)} style={{ flexGrow: s.value, flexBasis: 0 }} />
            ))}
        </div>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {segments.map((s) => (
            <li key={s.id} className="flex items-center gap-1.5">
              <span className={cn("size-2 flex-none rounded-sm", s.colorClass)} aria-hidden />
              <span className="text-muted-foreground">{s.label}</span>
              <span className="font-mono tabular-nums">{s.value.toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </div>

      <ul className="grid grid-cols-1 gap-x-8 gap-y-2.5 border-t border-border pt-4 text-xs sm:grid-cols-2">
        {edges.map((e) => (
          <li key={e.id} className="grid grid-cols-[4.5rem_minmax(0,1fr)_2.5rem] items-center gap-3">
            <span className="text-muted-foreground">{e.label}</span>
            <span className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
              <span className={cn("block h-full rounded-full", e.colorClass)} style={{ width: `${e.barPercent}%` }} />
            </span>
            <span className="text-right font-mono tabular-nums">{e.value.toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
