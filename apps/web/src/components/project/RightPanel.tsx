"use client";

import { Network, Terminal, BarChart2, LayoutDashboard } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GraphTab } from "./GraphTab";
import { QueryTab } from "./QueryTab";
import { AnalysisTab } from "./AnalysisTab";
import { OverviewTab } from "./OverviewTab";

export function RightPanel({ projectId }: { projectId: string }) {
  return (
    <Tabs defaultValue="overview" className="flex-1 flex flex-col overflow-hidden">
      <TabsList>
        <TabsTrigger value="overview" className="flex items-center gap-1.5">
          <LayoutDashboard className="size-3.5" />
          Overview
        </TabsTrigger>
        <TabsTrigger value="graph" className="flex items-center gap-1.5">
          <Network className="size-3.5" />
          Graph
        </TabsTrigger>
        <TabsTrigger value="query" className="flex items-center gap-1.5">
          <Terminal className="size-3.5" />
          Query
        </TabsTrigger>
        <TabsTrigger value="analysis" className="flex items-center gap-1.5">
          <BarChart2 className="size-3.5" />
          Analysis
        </TabsTrigger>
      </TabsList>

      <TabsContent value="overview">
        <OverviewTab projectId={projectId} />
      </TabsContent>
      <TabsContent value="graph">
        <GraphTab projectId={projectId} />
      </TabsContent>
      <TabsContent value="query">
        <QueryTab />
      </TabsContent>
      <TabsContent value="analysis">
        <AnalysisTab />
      </TabsContent>
    </Tabs>
  );
}
