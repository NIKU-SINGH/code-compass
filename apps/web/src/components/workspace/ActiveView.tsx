"use client";

import { LayoutDashboard, Orbit, Target } from "lucide-react";
import { TargetAnalysis } from "@/components/impact/TargetAnalysis";
import { ExplorerPanel } from "@/components/project/graph/ExplorerPanel";
import { InsightsDashboard } from "@/components/overview/InsightsDashboard";
import { NavRail, type NavRailItem } from "@/components/shell/NavRail";
import { useViewShortcuts } from "@/components/shell/useViewShortcuts";
import { useWorkspaceView } from "@/components/shell/useWorkspaceView";

const NAV_ITEMS: ReadonlyArray<NavRailItem> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, shortcut: "G O" },
  { id: "graph", label: "Graph", icon: Orbit, shortcut: "G G" },
  { id: "impact", label: "Impact", icon: Target, shortcut: "G I" },
];

const CHORD_KEYS = { o: "overview", g: "graph", i: "impact" } as const;

export function ActiveView() {
  const { view, setView } = useWorkspaceView();
  useViewShortcuts(CHORD_KEYS, setView);

  return (
    <div className="flex flex-1 min-h-0 min-w-0">
      <NavRail items={NAV_ITEMS} active={view} onSelect={setView} />
      <div className="flex flex-1 min-h-0 min-w-0 flex-col overflow-hidden">
        {view === "overview" && <InsightsDashboard />}
        {view === "graph" && <ExplorerPanel />}
        {view === "impact" && <TargetAnalysis />}
      </div>
    </div>
  );
}
