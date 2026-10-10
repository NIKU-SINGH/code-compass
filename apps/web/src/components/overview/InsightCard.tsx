import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { InsightRow } from "./InsightRow";
import type { InsightRowData } from "./insightCards";

interface InsightCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  badge?: string;
  rows: ReadonlyArray<InsightRowData>;
  emptyText: string;
  /** Row click handler; omit for non-navigable rows. */
  onSelect?: (row: InsightRowData) => void;
}

export function InsightCard({ title, description, icon: Icon, badge, rows, emptyText, onSelect }: InsightCardProps) {
  return (
    <Card className="flex min-w-0 flex-col overflow-hidden shadow-none">
      <div className="flex flex-col gap-1 border-b border-border px-3.5 py-3">
        <div className="flex items-center gap-2">
          <Icon className="size-4 flex-none text-muted-foreground" aria-hidden />
          <h3 className="text-sm font-semibold">{title}</h3>
          {badge && <Badge variant="secondary">{badge}</Badge>}
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {rows.length === 0 ? (
        <p className="px-3.5 py-6 text-center text-xs text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="flex flex-col py-1">
          {rows.map((row) => (
            <li key={row.id}>
              <InsightRow row={row} onSelect={onSelect} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
