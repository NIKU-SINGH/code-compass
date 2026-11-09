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

/** The one titled card every Overview section is built from, so spacing and headings never drift. */
export function SectionCard({ title, description, aside, className, children }: Props) {
  return (
    <Card className={cn("flex min-w-0 flex-col gap-4 px-5 py-4 shadow-none", className)}>
      <div className="flex flex-col gap-0.5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          {aside && <span className="text-xs text-muted-foreground tabular-nums">{aside}</span>}
        </div>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </Card>
  );
}
