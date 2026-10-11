import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";

interface InsightGroupProps {
  title: string;
  /** Small label next to the title, e.g. "Sample data". */
  note?: string;
  /** Explains `note` on hover. */
  noteTitle?: string;
  /** Typically two InsightCards. */
  children: ReactNode;
}

export function InsightGroup({ title, note, noteTitle, children }: InsightGroupProps) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 border-b border-border pb-1.5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
        {title}
        {note && (
          <Badge variant="outline" title={noteTitle} className="normal-case tracking-normal">
            {note}
          </Badge>
        )}
      </h2>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}
