"use client";

import { Network, Terminal, BarChart2 } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GraphTab } from "./GraphTab";
import { QueryTab } from "./QueryTab";
import { AnalysisTab } from "./AnalysisTab";

export function RightPanel({ projectId: _projectId }: { projectId: string }) {
  return (
    <Tabs defaultValue="graph" className="flex-1 flex flex-col overflow-hidden">
      <TabsList>
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

      <TabsContent value="graph">
        <GraphTab />
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
