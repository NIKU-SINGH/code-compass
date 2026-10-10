"use client";

import { Target, X } from "lucide-react";
import type { VisibleNode } from "./useExpandableGraph";
import { NODE_LABEL, NODE_TEXT_CLASS } from "./graphStyle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface Props {
  node: VisibleNode;
  connectionCount: number;
  onClose: () => void;
  onShowImpact: (node: VisibleNode) => void;
}

export function DetailsPanel({ node, connectionCount, onClose, onShowImpact }: Props) {
  return (
    <Card className="absolute top-3 right-3 w-[340px] max-h-[calc(100%-1.5rem)] overflow-y-auto bg-card/80 backdrop-blur-md shadow-lg z-20 text-xs flex flex-col">
      <div className="flex items-start justify-between gap-2 px-4 py-3 border-b border-border">
        <div className="min-w-0 flex flex-col gap-1.5">
          <Badge variant="outline" className={`w-fit ${NODE_TEXT_CLASS[node.type]}`}>
            {NODE_LABEL[node.type]}
          </Badge>
          <p className="font-mono font-semibold text-foreground text-sm break-all">{node.label}</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="size-6 text-muted-foreground hover:text-foreground flex-shrink-0 [&_svg]:size-3.5"
          aria-label="Close"
        >
          <X />
        </Button>
      </div>

      <div className="px-4 py-3 border-b border-border flex flex-col gap-1.5">
        <Row label="path" value={repoRelativePath(node.publicId)} />
        <Row label="id" value={node.publicId} />
        <Row
          label="connections"
          value={String(connectionCount)}
        />
      </div>

      <div className="px-4 py-3 flex flex-col gap-3">
        <Button onClick={() => onShowImpact(node)} className="w-full">
          <Target />
          Show impact
        </Button>
        <p className="text-muted-foreground">Source preview unavailable</p>
      </div>
    </Card>
  );
}

// The stored path may be absolute; the public id always carries the repo-relative one.
function repoRelativePath(publicId: string): string {
  return publicId.startsWith("file::") ? publicId.slice("file::".length) : publicId.split("::")[0];
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted-foreground flex-shrink-0">{label}</span>
      <span className="text-foreground text-right break-all font-mono text-[10px]">{value}</span>
    </div>
  );
}
