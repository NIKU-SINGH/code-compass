import { Orbit } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { ImpactResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KIND_STYLES, symbolLocation } from "./symbolKind";

interface TargetCardProps {
  result: ImpactResult;
  onShowInGraph: (id: string) => void;
}

export function TargetCard({ result, onShowInGraph }: TargetCardProps) {
  const { target } = result;
  const kind = KIND_STYLES[target.kind];
  const Icon = kind.icon;
  const location = symbolLocation(target);
  return (
    <Card className="flex items-start gap-4 p-4">
      <div
        className={cn("flex size-10 flex-none items-center justify-center rounded-lg", kind.tintClass, kind.textClass)}
      >
        <Icon className="size-5" aria-hidden />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="font-mono text-lg font-semibold tracking-tight">{target.name}</h2>
          <Badge variant="secondary" className={cn(kind.textClass, kind.tintClass)}>
            {kind.label}
          </Badge>
          {location && <span className="font-mono text-xs text-muted-foreground">{location}</span>}
        </div>
        {target.signature && (
          <div className="break-words font-mono text-xs text-muted-foreground">{target.signature}</div>
        )}
        <div className="text-sm">
          <span className="font-semibold">{result.total} affected</span>
          <span className="text-muted-foreground">
            {" "}
            · {result.affected_file_count} {result.affected_file_count === 1 ? "file" : "files"}
          </span>
        </div>
      </div>
      <Button variant="outline" size="sm" className="cursor-pointer" onClick={() => onShowInGraph(target.id)}>
        <Orbit className="size-3.5" aria-hidden />
        Show in graph
      </Button>
    </Card>
  );
}
