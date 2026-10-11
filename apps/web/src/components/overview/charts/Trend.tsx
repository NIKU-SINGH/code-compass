"use client";

import { Area, AreaChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { ChartCard } from "./ChartCard";

export interface TrendSeries {
  id: string;
  label: string;
  color: string;
  /** One value per entry of `labels`. */
  values: ReadonlyArray<number>;
}

interface Props {
  title: string;
  description?: string;
  aside?: string;
  /** X-axis labels, oldest first. */
  labels: ReadonlyArray<string>;
  series: ReadonlyArray<TrendSeries>;
  /** Appended to axis ticks, e.g. "%". */
  unit?: string;
  /** Fill under a single series instead of separate lines. */
  area?: boolean;
}

const HEIGHT = 200;

/**
 * Change over time: lines for several series, or a filled area for one. The legend is always
 * shown for more than one series, and the table view carries every value.
 */
export function Trend({ title, description, aside, labels, series, unit = "", area = false }: Props) {
  const config: ChartConfig = Object.fromEntries(
    series.map((s) => [s.id, { label: s.label, color: s.color }])
  );
  const data = labels.map((label, i) => ({
    label,
    ...Object.fromEntries(series.map((s) => [s.id, s.values[i] ?? 0])),
  }));
  // A plain array, not a fragment: recharts only finds axes, grid and legend among direct children.
  const axes = [
    <CartesianGrid key="grid" vertical={false} stroke="var(--border)" />,
    <XAxis key="x" dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />,
    <YAxis
      key="y"
      width={40}
      tickLine={false}
      axisLine={false}
      tickFormatter={(v: number) => `${v}${unit}`}
      domain={[0, "auto"]}
    />,
    <ChartTooltip key="tooltip" content={<ChartTooltipContent indicator="line" />} />,
    ...(series.length > 1
      ? [<ChartLegend key="legend" content={<ChartLegendContent />} />]
      : []),
  ];

  return (
    <ChartCard title={title} description={description} aside={aside}>
      <ChartContainer config={config} className="aspect-auto w-full" style={{ height: HEIGHT }}>
        {area ? (
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            {axes}
            {series.map((s) => (
              <Area
                key={s.id}
                dataKey={s.id}
                type="monotone"
                stroke={`var(--color-${s.id})`}
                strokeWidth={2}
                fill={`var(--color-${s.id})`}
                fillOpacity={0.16}
                dot={false}
                activeDot={{ r: 4, stroke: "var(--card)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        ) : (
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            {axes}
            {series.map((s) => (
              <Line
                key={s.id}
                dataKey={s.id}
                type="monotone"
                stroke={`var(--color-${s.id})`}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "var(--card)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        )}
      </ChartContainer>
    </ChartCard>
  );
}
