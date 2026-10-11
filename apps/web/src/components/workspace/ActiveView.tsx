"use client";

import { LayoutDashboard, Orbit, Target } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { TargetAnalysis } from "@/components/impact/TargetAnalysis";
import { ExplorerPanel } from "@/components/project/graph/ExplorerPanel";
import { InsightsDashboard } from "@/components/overview/InsightsDashboard";
import { NavRail, type NavRailItem } from "@/components/shell/NavRail";
import { useViewShortcuts } from "@/components/shell/useViewShortcuts";
import { useWorkspaceView, type WorkspaceView } from "@/components/shell/useWorkspaceView";

const NAV_ITEMS: ReadonlyArray<NavRailItem> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, shortcut: "G O" },
  { id: "graph", label: "Graph", icon: Orbit, shortcut: "G G" },
  { id: "impact", label: "Impact", icon: Target, shortcut: "G I" },
];

const CHORD_KEYS = { o: "overview", g: "graph", i: "impact" } as const;

export function ActiveView() {
  const { view, focus, setView } = useWorkspaceView();
  // Last focus seen per view, so leaving a view and coming back (rail or shortcut)
  // restores its target: Impact -> Overview -> Impact keeps the Impact target.
  const rememberedFocus = useRef<Partial<Record<WorkspaceView, string | null>>>({});
  useEffect(() => {
    rememberedFocus.current[view] = focus;
  }, [view, focus]);
  const selectView = useCallback(
    (next: WorkspaceView) => setView(next, rememberedFocus.current[next] ?? null),
    [setView],
  );
  useViewShortcuts(CHORD_KEYS, selectView);

  return (
    <div className="flex flex-1 min-h-0 min-w-0">
      <NavRail items={NAV_ITEMS} active={view} onSelect={selectView} />
      <div className="flex flex-1 min-h-0 min-w-0 flex-col overflow-hidden">
        {view === "overview" && <InsightsDashboard />}
        {view === "graph" && <ExplorerPanel />}
        {view === "impact" && <TargetAnalysis />}
      </div>
    </div>
  );
}
