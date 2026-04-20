"use client";

export type NodeType = "File" | "Class" | "Function" | "Method" | "ExternalDep" | "Field";
export type EdgeType = "CONTAINS" | "IMPORTS" | "INHERITS" | "CALLS" | "CALLS_EXTERN";
export type LayoutType = "force" | "tree" | "radial";

export interface FilterState {
  nodes: Record<NodeType, boolean>;
  edges: Record<EdgeType, boolean>;
  focusDepth: number | null;
  layout: LayoutType;
  showLabels: boolean;
}

export const DEFAULT_FILTER_STATE: FilterState = {
  nodes: {
    File:        true,
    Class:       true,
    Function:    true,
    Method:      true,
    ExternalDep: false,
    Field:       false,
  },
  edges: {
    CONTAINS:    true,
    IMPORTS:     true,
    INHERITS:    true,
    CALLS:       false,
    CALLS_EXTERN:false,
  },
  focusDepth: null,
  layout:     "force",
  showLabels: true,
};

const NODE_CONFIG: Array<{ type: NodeType; label: string; color: string }> = [
  { type: "File",        label: "File",         color: "oklch(0.588 0.217 264)" },
  { type: "Class",       label: "Class",        color: "#f59e0b" },
  { type: "Function",    label: "Function",     color: "#10b981" },
  { type: "Method",      label: "Method",       color: "#06b6d4" },
  { type: "ExternalDep", label: "External Dep", color: "#94a3b8" },
  { type: "Field",       label: "Field",        color: "#a78bfa" },
];

const EDGE_CONFIG: Array<{ type: EdgeType; label: string; color: string; dashed?: boolean }> = [
  { type: "CONTAINS",    label: "Contains",   color: "#10b981" },
  { type: "IMPORTS",     label: "Imports",    color: "oklch(0.588 0.217 264)" },
  { type: "INHERITS",    label: "Inherits",   color: "#f97316" },
  { type: "CALLS",       label: "Calls",      color: "rgba(255,255,255,0.25)", dashed: true },
  { type: "CALLS_EXTERN",label: "Ext. Calls", color: "#94a3b8",               dashed: true },
];

interface Props {
  state: FilterState;
  onChange: (state: FilterState) => void;
}

export function FilterPanel({ state, onChange }: Props) {
  function toggleNode(type: NodeType) {
    onChange({ ...state, nodes: { ...state.nodes, [type]: !state.nodes[type] } });
  }

  function toggleEdge(type: EdgeType) {
    onChange({ ...state, edges: { ...state.edges, [type]: !state.edges[type] } });
  }

  function setDepth(depth: number | null) {
    onChange({ ...state, focusDepth: depth });
  }

  function setLayout(layout: LayoutType) {
    onChange({ ...state, layout });
  }

  function toggleLabels() {
    onChange({ ...state, showLabels: !state.showLabels });
  }

  return (
    <div className="w-[210px] border-r border-border bg-card flex flex-col flex-shrink-0 overflow-y-auto text-sm">

      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <p className="text-xs font-semibold text-foreground">Graph Filters</p>
        <p className="text-xs text-muted-foreground mt-0.5">Customise what&apos;s visible</p>
      </div>

      {/* Nodes */}
      <Section title="Nodes">
        {NODE_CONFIG.map(({ type, label, color }) => (
          <ToggleRow
            key={type}
            label={label}
            on={state.nodes[type]}
            onToggle={() => toggleNode(type)}
            indicator={<span className="size-2 rounded-full flex-shrink-0" style={{ background: color }} />}
          />
        ))}
      </Section>

      {/* Relationships */}
      <Section title="Relationships">
        {EDGE_CONFIG.map(({ type, label, color, dashed }) => (
          <ToggleRow
            key={type}
            label={label}
            on={state.edges[type]}
            onToggle={() => toggleEdge(type)}
            indicator={
              <span
                className="w-5 flex-shrink-0"
                style={{
                  height:     dashed ? 0 : 2,
                  borderTop:  dashed ? `2px dashed ${color}` : "none",
                  background: dashed ? "none" : color,
                  borderRadius: 2,
                  marginTop:  dashed ? 1 : 0,
                }}
              />
            }
          />
        ))}
      </Section>

      {/* Focus Depth */}
      <Section title="Focus Depth" sub="Hops from selected node">
        <div className="flex flex-wrap gap-1.5">
          {([null, 1, 2, 3] as Array<number | null>).map((d) => (
            <button
              key={String(d)}
              onClick={() => setDepth(d)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                state.focusDepth === d
                  ? "bg-primary border-primary text-primary-foreground"
                  : "bg-muted border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {d === null ? "All" : `${d}`}
            </button>
          ))}
        </div>
      </Section>

      {/* Layout */}
      <Section title="Layout">
        <div className="flex gap-1">
          {(["force", "tree", "radial"] as LayoutType[]).map((l) => (
            <button
              key={l}
              onClick={() => setLayout(l)}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium border capitalize transition-colors ${
                state.layout === l
                  ? "border-primary text-foreground bg-muted"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
      </Section>

      {/* Display */}
      <Section title="Display">
        <div className="flex items-center justify-between">
          <span className={`text-xs ${state.showLabels ? "text-foreground" : "text-muted-foreground"}`}>
            Node labels
          </span>
          <Toggle on={state.showLabels} onToggle={toggleLabels} />
        </div>
      </Section>

    </div>
  );
}

function Section({
  title,
  sub,
  children,
}: {
  title: string;
  sub?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-4 py-3.5 border-b border-border flex flex-col gap-2">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        {title}
      </p>
      {sub && <p className="text-[10px] text-muted-foreground/60 -mt-1">{sub}</p>}
      {children}
    </div>
  );
}

function ToggleRow({
  label,
  on,
  onToggle,
  indicator,
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
  indicator: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 py-[3px]">
      {indicator}
      <span className={`flex-1 text-xs ${on ? "text-foreground" : "text-muted-foreground/50"}`}>
        {label}
      </span>
      <Toggle on={on} onToggle={onToggle} />
    </div>
  );
}

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`w-7 h-3.5 rounded-full relative transition-colors flex-shrink-0 ${
        on ? "bg-primary" : "bg-muted-foreground/20"
      }`}
    >
      <span
        className={`absolute top-[2px] size-[10px] rounded-full bg-white transition-[left] ${
          on ? "left-[14px]" : "left-[2px]"
        }`}
      />
    </button>
  );
}
