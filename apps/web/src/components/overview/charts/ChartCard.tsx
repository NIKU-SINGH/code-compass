import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  title: string;
  description?: string;
  /** Right-aligned note in the header, e.g. a total. */
  aside?: string;
  className?: string;
  children: ReactNode;
}

/** Titled card shared by every Overview chart. */
export function ChartCard({ title, description, aside, className, children }: Props) {
  return (
    <Card className={cn("flex min-w-0 flex-col gap-3 px-4 py-3.5 shadow-none", className)}>
      <div className="flex flex-col gap-0.5">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">{title}</h3>
          {aside && <span className="text-xs text-muted-foreground tabular-nums">{aside}</span>}
        </div>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </Card>
  );
}
