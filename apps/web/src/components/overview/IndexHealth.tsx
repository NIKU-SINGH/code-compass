import { SectionCard } from "./SectionCard";
import { cn } from "@/lib/utils";

export interface HealthIssue {
  id: string;
  label: string;
  count: number;
  /** Tailwind background class for the dot: amber for degraded results, red for failures. */
  dotClass: string;
}

interface Props {
  /** 0-100. */
  resolvedPercent: number;
  issues: ReadonlyArray<HealthIssue>;
  note: string;
}

/** How trustworthy the index is: share of calls resolved, and what could not be. */
export function IndexHealth({ resolvedPercent, issues, note }: Props) {
  return (
    <SectionCard title="Index health" description={note}>
      <div className="flex flex-col gap-2.5">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-semibold tracking-tight">{resolvedPercent}%</span>
          <span className="text-xs text-muted-foreground">of calls resolved</span>
        </div>
        <div
          role="img"
          aria-label={`${resolvedPercent}% of calls resolved`}
          className="flex h-2.5 overflow-hidden rounded-full bg-kind-class/40"
        >
          <span className="h-full rounded-full bg-kind-function" style={{ width: `${resolvedPercent}%` }} />
        </div>
      </div>

      <ul className="flex flex-col gap-1.5 text-xs">
        {issues.map((i) => (
          <li key={i.id} className="flex items-center gap-2">
            <span className={cn("size-2 flex-none rounded-full", i.dotClass)} aria-hidden />
            <span className="flex-1 text-muted-foreground">{i.label}</span>
            <span className="font-mono tabular-nums">{i.count.toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
