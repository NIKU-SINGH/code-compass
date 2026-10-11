import type { ReactNode } from "react";

interface InsightGroupProps {
  title: string;
  /** Typically two cards. */
  children: ReactNode;
}

export function InsightGroup({ title, children }: InsightGroupProps) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-xs font-medium uppercase tracking-widest text-muted-foreground">{title}</h3>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}
