"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { VisibleNode } from "./useExpandableGraph";
import { NODE_COLOR, NODE_LABEL } from "./graphStyle";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface FileContentResponse {
  path: string;
  content: string;
  truncated: boolean;
}

interface Props {
  node: VisibleNode;
  connectionCount: number;
  onClose: () => void;
}

export function DetailsPanel({ node, connectionCount, onClose }: Props) {
  const [code, setCode] = useState<string | null>(null);
  const [loadingCode, setLoadingCode] = useState(false);
  const [codeError, setCodeError] = useState<string | null>(null);

  // Collapse any open code preview whenever a different node is selected.
  useEffect(() => {
    setCode(null);
    setCodeError(null);
    setLoadingCode(false);
  }, [node.id]);

  async function handleViewCode() {
    if (code !== null) {
      setCode(null);
      return;
    }
    setLoadingCode(true);
    setCodeError(null);
    try {
      const res = await apiFetch<FileContentResponse>(
        `/api/repo/file?path=${encodeURIComponent(node.filePath)}`
      );
      setCode(res.truncated ? `${res.content}\n\n… (truncated)` : res.content);
    } catch (e) {
      setCodeError(e instanceof Error ? e.message : "Failed to load file");
    } finally {
      setLoadingCode(false);
    }
  }

  return (
    <div className="absolute top-3 right-3 w-[340px] max-h-[calc(100%-1.5rem)] overflow-y-auto bg-card/95 backdrop-blur border border-border rounded-lg shadow-lg z-20 text-xs flex flex-col">
      <div className="flex items-start justify-between gap-2 px-4 py-3 border-b border-border">
        <p className="font-semibold text-foreground text-sm">{node.label}</p>
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

      <div className="px-4 py-3 flex items-center gap-2 border-b border-border">
        <span
          className="px-1.5 py-0.5 rounded text-[10px] font-medium border"
          style={{ color: NODE_COLOR[node.type], borderColor: NODE_COLOR[node.type] }}
        >
          {NODE_LABEL[node.type]}
        </span>
        <span className="text-muted-foreground">
          {connectionCount} connection{connectionCount === 1 ? "" : "s"}
        </span>
      </div>

      <div className="px-4 py-3 border-b border-border flex flex-col gap-1.5">
        <Row label="id" value={node.id} mono />
        <Row label="type" value={node.type} />
        <Row label="file path" value={node.filePath} mono />
      </div>

      <div className="px-4 py-3">
        <Button
          variant="outline"
          onClick={handleViewCode}
          disabled={loadingCode}
          className="w-full"
        >
          {loadingCode ? "Loading…" : code !== null ? "Hide code" : "View code"}
        </Button>
        {codeError && <p className="text-destructive mt-2">{codeError}</p>}
        {code !== null && (
          <pre className="mt-3 max-h-64 overflow-auto bg-muted/50 rounded-md p-2 text-[10px] leading-relaxed whitespace-pre-wrap break-words font-mono">
            {code}
          </pre>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted-foreground flex-shrink-0">{label}</span>
      <span className={`text-foreground text-right break-all ${mono ? "font-mono text-[10px]" : ""}`}>
        {value}
      </span>
    </div>
  );
}
