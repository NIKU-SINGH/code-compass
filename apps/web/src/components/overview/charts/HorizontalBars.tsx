"use client";

import { Bar, BarChart, LabelList, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { ChartCard } from "./ChartCard";
import { SINGLE_COLOR } from "./palette";

export interface BarRow {
  id: string;
  label: string;
  value: number;
  /** Text at the bar's end instead of the bare value, e.g. "5 of 8". */
  detail?: string;
}

interface Props {
  title: string;
  description?: string;
  aside?: string;
  rows: ReadonlyArray<BarRow>;
  /** What `value` counts, for the tooltip and table, e.g. "Commits". */
  valueLabel: string;
  color?: string;
}

const ROW_PX = 32;
const MAX_LABEL = 26;

/** Paths read best from their end: `…/billing/invoice.py`. */
function shorten(label: string): string {
  return label.length <= MAX_LABEL ? label : `…${label.slice(-(MAX_LABEL - 1))}`;
}

/** One-series ranking as horizontal bars; one hue because the labels already carry identity. */
export function HorizontalBars({ title, description, aside, rows, valueLabel, color = SINGLE_COLOR }: Props) {
  const config: ChartConfig = { value: { label: valueLabel, color } };
  const data = rows.map((r) => ({ ...r, detail: r.detail ?? r.value.toLocaleString() }));

  return (
    <ChartCard title={title} description={description} aside={aside}>
      <ChartContainer
        config={config}
        className="aspect-auto w-full"
        style={{ height: Math.max(rows.length, 1) * ROW_PX + 8 }}
      >
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }} barCategoryGap={10}>
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis
            type="category"
            dataKey="label"
            width={180}
            tickLine={false}
            axisLine={false}
            tickFormatter={shorten}
            tick={{ fill: "var(--muted-foreground)", fontSize: 11, fontFamily: "var(--font-mono, monospace)" }}
          />
          <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={<ChartTooltipContent hideLabel />} />
          <Bar dataKey="value" fill="var(--color-value)" radius={[0, 4, 4, 0]} barSize={12} isAnimationActive={false}>
            <LabelList
              dataKey="detail"
              position="right"
              fill="var(--foreground)"
              fontSize={11}
              fontFamily="var(--font-mono, monospace)"
            />
          </Bar>
        </BarChart>
      </ChartContainer>
    </ChartCard>
  );
}
