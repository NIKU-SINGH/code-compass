"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface EntryPoint {
  path: string;
  module_name: string;
}

interface OverviewData {
  project_id: string;
  file_count: number;
  class_count: number;
  function_count: number;
  edge_count: number;
  entry_points: EntryPoint[];
}

function tagForModule(moduleName: string): string {
  if (moduleName.includes("main")) return "entry";
  if (moduleName.includes("server") || moduleName.includes("api")) return "server";
  if (moduleName.includes("settings") || moduleName.includes("config")) return "config";
  return "core";
}

export function OverviewTab() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<OverviewData>("/api/repo/overview")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-6">
        <p className="text-sm font-medium text-foreground">No index found</p>
        <p className="text-xs text-muted-foreground">
          Run{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
            compass ingest ./repo
          </code>{" "}
          first to index this repository.
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Loading…
      </div>
    );
  }

  const totalModules = data.file_count;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 py-7 max-w-3xl">

        {/* Repo header */}
        <div className="mb-5">
          <h1 className="text-xl font-bold tracking-tight">{data.project_id}</h1>
          <p className="text-xs text-muted-foreground mt-1">Python · {data.file_count} files</p>
        </div>

        <div className="h-px bg-border mb-6" />

        {/* Stats strip */}
        <div className="grid grid-cols-4 border border-border rounded-lg overflow-hidden mb-8">
          {[
            { label: "Files",     value: data.file_count },
            { label: "Functions", value: data.function_count },
            { label: "Classes",   value: data.class_count },
            { label: "Edges",     value: data.edge_count },
          ].map((s, i) => (
            <div
              key={s.label}
              className={`px-4 py-3.5 ${i < 3 ? "border-r border-border" : ""}`}
            >
              <div className="text-lg font-bold">{s.value.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Summary
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            <span className="text-foreground font-medium">{data.project_id}</span> is a Python
            codebase with {data.file_count} files across {totalModules} modules,{" "}
            {data.class_count} classes, and {data.function_count} functions connected by{" "}
            {data.edge_count.toLocaleString()} edges in the knowledge graph.
          </p>
        </div>

        {/* Starting Points */}
        {data.entry_points.length > 0 && (
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Starting Points
            </p>
            <div className="border border-border rounded-lg overflow-hidden">
              {data.entry_points.map((ep) => {
                const tag = tagForModule(ep.module_name);
                return (
                  <div
                    key={ep.path}
                    className="flex items-baseline gap-3 px-4 py-2.5 border-b border-border last:border-b-0 bg-card"
                  >
                    <span className="text-[10px] font-medium text-muted-foreground bg-muted border border-border rounded px-1.5 py-px flex-shrink-0">
                      {tag}
                    </span>
                    <span className="font-mono text-xs text-foreground truncate">
                      {ep.path}
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto flex-shrink-0">
                      {ep.module_name}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}


      </div>
    </div>
  );
}

