import { Target } from "lucide-react";

export function ImpactPlaceholder() {
  return (
    <div className="flex h-full items-center justify-center p-10">
      <div className="flex max-w-sm flex-col items-center gap-2 rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
        <Target className="size-6" />
        <div className="font-semibold text-foreground">Impact analysis</div>
        <div className="text-sm">Select a symbol to see what it affects.</div>
      </div>
    </div>
  );
}
