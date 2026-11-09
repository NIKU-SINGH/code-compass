"use client";

import { Minus, Plus } from "lucide-react";
import type { NodeType, EdgeType } from "./useGraphData";
import { NODE_DOT_CLASS, NODE_LABEL, EDGE_LINE_CLASS, EDGE_LABEL } from "./graphStyle";
import { FilterRow } from "./FilterRow";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

const NODE_ORDER: NodeType[] = ["File", "Class", "Function", "Method", "ExternalDep"];
const EDGE_ORDER: EdgeType[] = ["CONTAINS", "IMPORTS", "INHERITS", "CALLS", "CALLS_EXTERN"];

interface Props {
  typeVisibility: Record<NodeType, boolean>;
  typeCounts: Record<NodeType, number>;
  typeTotals: Record<NodeType, number>;
  onToggleType: (type: NodeType) => void;
  edgeTypeVisibility: Record<EdgeType, boolean>;
  edgeTypeCounts: Record<EdgeType, number>;
  edgeTypeTotals: Record<EdgeType, number>;
  onToggleEdgeType: (type: EdgeType) => void;
  showLabels: boolean;
  onToggleLabels: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export function GraphLegend({
  typeVisibility,
  typeCounts,
  typeTotals,
  onToggleType,
  edgeTypeVisibility,
  edgeTypeCounts,
  edgeTypeTotals,
  onToggleEdgeType,
  showLabels,
  onToggleLabels,
  onZoomIn,
  onZoomOut,
}: Props) {
  return (
    <Card className="absolute bottom-4 left-4 w-[220px] max-h-[calc(100%-2rem)] overflow-y-auto bg-card/80 backdrop-blur-md p-3.5 text-xs z-10 flex flex-col gap-3.5">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
          Entities
        </p>
        <div className="flex flex-col">
          {NODE_ORDER.map((type) => (
            <FilterRow
              key={type}
              id={`filter-node-${type}`}
              label={NODE_LABEL[type]}
              count={typeCounts[type]}
              total={typeTotals[type]}
              enabled={typeVisibility[type]}
              onToggle={() => onToggleType(type)}
              marker={
                <span
                  className={`size-2 rounded-full flex-shrink-0 ${NODE_DOT_CLASS[type]} ${typeVisibility[type] ? "" : "opacity-25"}`}
                />
              }
            />
          ))}
        </div>
      </div>

      <div className="border-t border-border pt-3">
        <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
          Relationships
        </p>
        <div className="flex flex-col">
          {EDGE_ORDER.map((type) => (
            <FilterRow
              key={type}
              id={`filter-edge-${type}`}
              label={EDGE_LABEL[type]}
              count={edgeTypeCounts[type]}
              total={edgeTypeTotals[type]}
              enabled={edgeTypeVisibility[type]}
              onToggle={() => onToggleEdgeType(type)}
              marker={
                <span
                  className={`w-3 h-0.5 rounded-full flex-shrink-0 ${EDGE_LINE_CLASS[type]} ${edgeTypeVisibility[type] ? "" : "opacity-25"}`}
                />
              }
            />
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
    </Card>
  );
}
