"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function QueryTab() {
  const [query, setQuery] = useState("");

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Query input area */}
      <div className="p-4 border-b border-border shrink-0">
        <div className="flex gap-2">
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="MATCH (n:Function)-[:CALLS]->(m) RETURN n, m LIMIT 25"
            rows={3}
            className="resize-none text-xs font-mono"
          />
          <Button size="icon" disabled={!query.trim()} className="shrink-0 size-9 mt-auto">
            <Play className="size-3.5" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Run graph queries against the code index
        </p>
      </div>

      {/* Results area */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex items-center justify-center h-full text-muted-foreground">
          <p className="text-sm">Run a query to see results</p>
        </div>
      </div>
    </div>
  );
}
