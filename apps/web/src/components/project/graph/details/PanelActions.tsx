"use client";

import type { ReactNode } from "react";
import { Code2, LayoutList, Maximize2, Target } from "lucide-react";
import { cn } from "@/lib/utils";

export type PanelView = "overview" | "source";

interface Props {
  view: PanelView;
  onViewChange: (view: PanelView) => void;
  /** Whether the node has source to show; hides the Source view when it doesn't. */
  hasSource: boolean;
  onImpact: () => void;
  /** Omit when the node has nothing to expand. */
  onExpand?: () => void;
}

interface SegmentProps {
  icon: ReactNode;
  label: string;
  hint: string;
  onClick: () => void;
  /** Set for the two views, one of which is always active; omit for one-shot actions. */
  active?: boolean;
}

function Segment({ icon, label, hint, onClick, active }: SegmentProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={hint}
      aria-pressed={active}
      className={cn(
        "flex h-8 flex-1 cursor-pointer items-center justify-center gap-1.5 text-xs transition-colors",
        "hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        active ? "bg-muted font-medium text-foreground" : "text-foreground/80"
      )}
    >
      <span className="[&_svg]:size-3.5" aria-hidden>
        {icon}
      </span>
      {label}
    </button>
  );
}

/**
 * One row of controls: the two views of the node (Overview, Source; exactly one is active) followed
 * by the one-shot actions (Impact, Expand), which never stay highlighted.
 */
export function PanelActions({ view, onViewChange, hasSource, onImpact, onExpand }: Props) {
  return (
    <div role="toolbar" aria-label="Node views and actions" className="flex divide-x divide-border overflow-hidden rounded-md border border-border">
      <Segment
        icon={<LayoutList />}
        label="Overview"
        hint="Everything this node connects to"
        onClick={() => onViewChange("overview")}
        active={view === "overview"}
      />
      {hasSource && (
        <Segment
          icon={<Code2 />}
          label="Source"
          hint="The code"
          onClick={() => onViewChange("source")}
          active={view === "source"}
        />
      )}
      <Segment icon={<Target />} label="Impact" hint="Show what a change to this could affect" onClick={onImpact} />
      {onExpand && (
        <Segment icon={<Maximize2 />} label="Expand" hint="Reveal this node's neighbours in the graph" onClick={onExpand} />
      )}
    </div>
  );
}
