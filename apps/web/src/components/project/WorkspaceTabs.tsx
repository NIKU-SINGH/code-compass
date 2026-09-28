"use client";

import { Network, LayoutDashboard } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GraphTab } from "./GraphTab";
import { OverviewTab } from "./OverviewTab";

export function WorkspaceTabs() {
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
      </TabsList>

      <TabsContent value="overview">
        <OverviewTab />
      </TabsContent>
      <TabsContent value="graph">
        <GraphTab />
      </TabsContent>
    </Tabs>
  );
}
