import type { ReactNode } from "react";

interface InsightGroupProps {
  title: string;
  /** Typically two InsightCards. */
  children: ReactNode;
}

export function InsightGroup({ title, children }: InsightGroupProps) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="border-b border-border pb-1.5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">{title}</h2>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}
