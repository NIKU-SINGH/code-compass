"use client";

import { Cell, Pie, PieChart } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { SectionCard } from "../SectionCard";

export interface DonutSegment {
  id: string;
  label: string;
  value: number;
  /** CSS colour, usually a `var(--token)`. */
  color: string;
}

interface Props {
  title: string;
  description?: string;
  aside?: string;
  segments: ReadonlyArray<DonutSegment>;
  /** Figure printed in the hole. */
  centre: { value: string; caption: string };
}

/** Part-to-whole donut with a centre figure and an always-on legend. */
export function Donut({ title, description, aside, segments, centre }: Props) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const shown = segments.filter((s) => s.value > 0);
  const config: ChartConfig = Object.fromEntries(
    segments.map((s) => [s.id, { label: s.label, color: s.color }])
  );

  return (
    <SectionCard title={title} description={description} aside={aside}>
      <div className="flex flex-col items-center gap-4 sm:flex-row">
        <div className="relative size-44 flex-none">
          <ChartContainer config={config} className="aspect-square size-full">
            <PieChart>
              <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="id" />} />
              <Pie
                data={shown}
                dataKey="value"
                nameKey="id"
                innerRadius="68%"
                outerRadius="100%"
                paddingAngle={2}
                cornerRadius={3}
                stroke="var(--card)"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {shown.map((s) => (
                  <Cell key={s.id} fill={s.color} />
                ))}
              </Pie>
            </PieChart>
          </ChartContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-semibold tracking-tight">{centre.value}</span>
            <span className="text-[11px] text-muted-foreground">{centre.caption}</span>
          </div>
        </div>
        <ul className="grid w-full min-w-0 flex-1 gap-1.5 text-xs">
          {segments.map((s) => (
            <li key={s.id} className="flex items-center gap-2">
              <span className="size-2.5 flex-none rounded-full" style={{ background: s.color }} aria-hidden />
              <span className="min-w-0 flex-1 truncate text-muted-foreground">{s.label}</span>
              <span className="font-mono tabular-nums">{s.value.toLocaleString()}</span>
              <span className="w-12 text-right font-mono tabular-nums text-muted-foreground">
                {total > 0 ? `${Math.round((s.value / total) * 1000) / 10}%` : "0%"}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </SectionCard>
  );
}
