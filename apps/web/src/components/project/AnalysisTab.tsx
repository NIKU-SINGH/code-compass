import { FileCode2, GitBranch, Package, Layers } from "lucide-react";

const STATS = [
  { label: "Files indexed", value: "—", icon: FileCode2 },
  { label: "Functions", value: "—", icon: GitBranch },
  { label: "Dependencies", value: "—", icon: Package },
  { label: "Modules", value: "—", icon: Layers },
];

export function AnalysisTab() {
  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="grid grid-cols-2 gap-3 mb-6">
        {STATS.map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-border bg-card p-3 flex flex-col gap-2"
          >
            <div className="flex items-center gap-2 text-muted-foreground">
              <stat.icon className="size-3.5" />
              <span className="text-xs">{stat.label}</span>
            </div>
            <span className="text-2xl font-semibold text-foreground">{stat.value}</span>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm font-medium text-foreground mb-1">Top Entry Points</p>
        <p className="text-xs text-muted-foreground">
          Analysis data will populate once the project is indexed.
        </p>
      </div>
    </div>
  );
}
