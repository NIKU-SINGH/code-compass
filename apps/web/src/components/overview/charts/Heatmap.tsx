import { Bot, User } from "lucide-react";
import { ChartCard } from "./ChartCard";
import { SINGLE_COLOR } from "./palette";

export interface HeatColumn {
  id: string;
  label: string;
  kind: "person" | "agent";
}

export interface HeatRow {
  id: string;
  label: string;
  /** Percent 0-100 per column id; missing means 0. */
  values: Readonly<Record<string, number>>;
}

interface Props {
  title: string;
  description?: string;
  columns: ReadonlyArray<HeatColumn>;
  rows: ReadonlyArray<HeatRow>;
}

const MAX_TINT = 78;

/** Cell tint: one hue, darker for more. 0 stays empty. */
function tint(percent: number): string {
  return percent > 0
    ? `color-mix(in oklab, ${SINGLE_COLOR} ${Math.round((percent / 100) * MAX_TINT + 8)}%, transparent)`
    : "transparent";
}

/** Matrix of share per row and column, with a scale legend; the cells themselves are the table. */
export function Heatmap({ title, description, columns, rows }: Props) {
  return (
    <ChartCard title={title} description={description} className="lg:col-span-2">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-xs">
          <thead>
            <tr>
              <th scope="col" className="w-36 text-left font-normal text-muted-foreground">
                Area
              </th>
              {columns.map((c) => {
                const Icon = c.kind === "agent" ? Bot : User;
                return (
                  <th key={c.id} scope="col" className="px-1 pb-1 align-bottom font-normal text-muted-foreground">
                    <span className="flex flex-col items-center gap-1 text-center leading-tight">
                      <Icon className="size-3" aria-hidden />
                      {c.label}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <th scope="row" className="truncate text-left font-mono font-normal">
                  {row.label}
                </th>
                {columns.map((c) => {
                  const v = row.values[c.id] ?? 0;
                  return (
                    <td
                      key={c.id}
                      title={`${row.label} · ${c.label}: ${v}%`}
                      style={{ background: tint(v) }}
                      className="h-9 min-w-14 rounded text-center font-mono tabular-nums ring-1 ring-inset ring-border/60"
                    >
                      {v > 0 ? `${v}%` : <span className="text-muted-foreground/60">–</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
        <span>0%</span>
        <span
          className="h-2 w-28 rounded-full ring-1 ring-border/60"
          style={{ background: `linear-gradient(to right, ${tint(0)}, ${tint(100)})` }}
          aria-hidden
        />
        <span>100% of the area&apos;s lines</span>
      </div>
    </ChartCard>
  );
}
