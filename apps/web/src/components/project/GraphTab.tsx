import { Network } from "lucide-react";

export function GraphTab({ projectId: _projectId }: { projectId: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
      <div className="size-12 rounded-xl bg-muted flex items-center justify-center">
        <Network className="size-6" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-foreground">Graph View</p>
        <p className="text-xs mt-1">Code graph visualization will appear here</p>
      </div>
    </div>
  );
}
