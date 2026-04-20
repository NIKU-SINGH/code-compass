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

export function OverviewTab({ projectId }: { projectId: string }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<OverviewData>("/api/repo/overview")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [projectId]);

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-6">
        <p className="text-sm font-medium text-foreground">No index found</p>
        <p className="text-xs text-muted-foreground">
          Run{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
            compass index ./repo
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

        {/* Architecture diagram */}
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Architecture
          </p>
          <div className="border border-border rounded-lg bg-card p-5">
            <ArchDiagram />
          </div>
        </div>

      </div>
    </div>
  );
}

function ArchDiagram() {
  return (
    <svg
      viewBox="0 0 620 290"
      width="100%"
      xmlns="http://www.w3.org/2000/svg"
      style={{ fontFamily: "inherit" }}
    >
      <defs>
        <marker id="arr-fwd" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,1.5 L5,3 L0,4.5" fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.35" />
        </marker>
        <marker id="arr-bwd" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">
          <path d="M6,1.5 L1,3 L6,4.5" fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.35" />
        </marker>
      </defs>

      {/* Actor boxes */}
      {[
        { x: 10,  label: "compass-cli" },
        { x: 160, label: "compass-core" },
        { x: 310, label: "FastAPI" },
        { x: 460, label: "React frontend" },
      ].map(({ x, label }) => (
        <g key={label}>
          <rect x={x} y={10} width={110} height={34} rx="5"
            fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
          <text x={x + 55} y={31} textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.7)" fontWeight="500">
            {label}
          </text>
        </g>
      ))}

      {/* LadybugDB header box */}
      <rect x="235" y={10} width="110" height="34" rx="5"
        fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      <text x="290" y={31} textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.7)" fontWeight="500">
        LadybugDB
      </text>

      {/* Lifelines */}
      {[65, 215, 365, 515].map((x) => (
        <line key={x} x1={x} y1={44} x2={x} y2={255}
          stroke="rgba(255,255,255,0.07)" strokeWidth="1" strokeDasharray="5,4" />
      ))}
      <line x1="290" y1={44} x2="290" y2={255}
        stroke="rgba(255,255,255,0.07)" strokeWidth="1" strokeDasharray="5,4" />

      {/* LadybugDB footer box */}
      <rect x="235" y={255} width="110" height="34" rx="5"
        fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      <text x="290" y={276} textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.7)" fontWeight="500">
        LadybugDB
      </text>

      {/* Step 1: CLI → core */}
      <circle cx="52" cy="80" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="52" y="84" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">1</text>
      <line x1="65" y1="80" x2="210" y2="80" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="137" y="74" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">compass index ./repo</text>

      {/* Step 2: core → DB */}
      <circle cx="202" cy="112" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="202" y="116" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">2</text>
      <line x1="215" y1="112" x2="278" y2="112" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="246" y="106" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">write graph</text>

      {/* Step 3: CLI → FastAPI */}
      <circle cx="52" cy="148" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="52" y="152" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">3</text>
      <line x1="65" y1="148" x2="360" y2="148" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="212" y="142" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">compass serve</text>

      {/* Step 4: React → FastAPI */}
      <circle cx="503" cy="180" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="503" y="184" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">4</text>
      <line x1="505" y1="180" x2="380" y2="180" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-bwd)" />
      <text x="442" y="174" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">GET /api/repo/graph</text>

      {/* Step 5: FastAPI → DB */}
      <circle cx="352" cy="214" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="352" y="218" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">5</text>
      <line x1="357" y1="214" x2="303" y2="214" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-bwd)" />
      <text x="330" y="208" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">Cypher</text>

      {/* Step 6: DB → FastAPI */}
      <circle cx="278" cy="236" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="278" y="240" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">6</text>
      <line x1="283" y1="236" x2="357" y2="236" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="320" y="230" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">graph data</text>
    </svg>
  );
}
