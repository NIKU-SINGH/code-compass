import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatTileProps {
  label: string;
  value: number;
  /** One line saying what the number counts. */
  detail: string;
  /** Tailwind background class from the `--kind-*` / `--edge-*` tokens, matching the graph legend. */
  colorClass: string;
}

export function StatTile({ label, value, detail, colorClass }: StatTileProps) {
  return (
    <Card className="flex flex-col gap-1 px-5 py-4 shadow-none">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <span className={cn("size-2 flex-none rounded-sm", colorClass)} aria-hidden />
        {label}
      </div>
      <div className="text-2xl font-semibold tabular-nums tracking-tight">{value.toLocaleString()}</div>
      <p className="text-xs text-muted-foreground">{detail}</p>
    </Card>
  );
}
