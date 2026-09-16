"use client";

import { Minus, Plus } from "lucide-react";
import type { NodeType, EdgeType } from "./useGraphData";
import { NODE_COLOR, NODE_LABEL, EDGE_COLOR, EDGE_LABEL } from "./graphStyle";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

const NODE_ORDER: NodeType[] = ["File", "Class", "Function", "Method", "ExternalDep", "Field"];
const EDGE_ORDER: EdgeType[] = ["CONTAINS", "IMPORTS", "INHERITS", "CALLS", "CALLS_EXTERN"];

interface Props {
  typeVisibility: Record<NodeType, boolean>;
  typeCounts: Record<NodeType, number>;
  onToggleType: (type: NodeType) => void;
  edgeTypeVisibility: Record<EdgeType, boolean>;
  edgeTypeCounts: Record<EdgeType, number>;
  onToggleEdgeType: (type: EdgeType) => void;
  showLabels: boolean;
  onToggleLabels: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export function GraphLegend({
  typeVisibility,
  typeCounts,
  onToggleType,
  edgeTypeVisibility,
  edgeTypeCounts,
  onToggleEdgeType,
  showLabels,
  onToggleLabels,
  onZoomIn,
  onZoomOut,
}: Props) {
  return (
    <div className="absolute bottom-4 left-4 w-[220px] max-h-[calc(100%-2rem)] overflow-y-auto bg-card/95 backdrop-blur border border-border rounded-lg p-3.5 text-xs z-10 flex flex-col gap-3.5">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
          Entities
        </p>
        <div className="flex flex-col gap-1.5">
          {NODE_ORDER.filter((t) => typeCounts[t] > 0 || typeVisibility[t]).map((type) => (
            <Button
              key={type}
              variant="ghost"
              onClick={() => onToggleType(type)}
              className="flex items-center gap-2 w-full h-auto justify-start px-1.5 py-1 font-normal"
            >
              <span
                className="size-2 rounded-full flex-shrink-0"
                style={{ background: NODE_COLOR[type], opacity: typeVisibility[type] ? 1 : 0.25 }}
              />
              <span
                className={`flex-1 text-left ${typeVisibility[type] ? "text-foreground" : "text-muted-foreground/50"}`}
              >
                {NODE_LABEL[type]}
              </span>
              <span className="text-muted-foreground">{typeCounts[type]}</span>
            </Button>
          ))}
        </div>
      </div>

      <div className="border-t border-border pt-3">
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
          Relationships
        </p>
        <div className="flex flex-col gap-1.5">
          {EDGE_ORDER.filter((t) => edgeTypeCounts[t] > 0 || edgeTypeVisibility[t]).map((type) => (
            <Button
              key={type}
              variant="ghost"
              onClick={() => onToggleEdgeType(type)}
              className="flex items-center gap-2 w-full h-auto justify-start px-1.5 py-1 font-normal"
            >
              <span
                className="w-3 h-0.5 rounded-full flex-shrink-0"
                style={{ background: EDGE_COLOR[type], opacity: edgeTypeVisibility[type] ? 1 : 0.25 }}
              />
              <span
                className={`flex-1 text-left ${edgeTypeVisibility[type] ? "text-foreground" : "text-muted-foreground/50"}`}
              >
                {EDGE_LABEL[type]}
              </span>
              <span className="text-muted-foreground">{edgeTypeCounts[type]}</span>
            </Button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-border pt-3">
        <span className="text-foreground">Show labels</span>
        <Switch checked={showLabels} onCheckedChange={onToggleLabels} />
      </div>

      <div className="flex items-center justify-between border-t border-border pt-3">
        <span className="text-foreground">Zoom</span>
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="icon"
            onClick={onZoomOut}
            aria-label="Zoom out"
            className="size-6 text-muted-foreground hover:text-foreground [&_svg]:size-3"
          >
            <Minus />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={onZoomIn}
            aria-label="Zoom in"
            className="size-6 text-muted-foreground hover:text-foreground [&_svg]:size-3"
          >
            <Plus />
          </Button>
        </div>
      </div>
    </div>
  );
}
