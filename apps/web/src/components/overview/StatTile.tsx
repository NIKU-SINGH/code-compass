import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";

interface StatTileProps {
  label: string;
  value: number;
  icon: LucideIcon;
}

export function StatTile({ label, value, icon: Icon }: StatTileProps) {
  return (
    <Card className="flex flex-col gap-2 px-4 py-3.5 shadow-none">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="size-3.5" aria-hidden />
        {label}
      </div>
      <div className="text-2xl font-semibold tabular-nums tracking-tight">{value.toLocaleString()}</div>
    </Card>
  );
}
