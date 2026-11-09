"use client";

import { useEffect, useState } from "react";
import { Check, Copy, PanelRightClose } from "lucide-react";
import type { NodeDetail, SymbolRef } from "@/lib/api";
import type { VisibleNode } from "./useExpandableGraph";
import { NODE_LABEL, NODE_TEXT_CLASS } from "./graphStyle";
import { Overview } from "./details/Overview";
import { PanelActions, type PanelView } from "./details/PanelActions";
import { SourceCode } from "./details/SourceCode";
import { sectionsFor } from "./details/relatedSections";
import { metaChips, shortPath } from "./details/meta";
import { iconForKind, locationLabel } from "./details/symbolLabel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/InlineError";
import { RetryButton } from "@/components/ui/RetryButton";
import { Skeleton } from "@/components/ui/skeleton";

interface Props {
  node: VisibleNode;
  /** Loaded details for `node`; null while loading, on error, or when the backend has none. */
  detail: NodeDetail | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onClose: () => void;
  onShowImpact: (node: VisibleNode) => void;
  onExpand: (node: VisibleNode) => void;
  canSelect: (symbol: SymbolRef) => boolean;
  onSelectRelated: (symbol: SymbolRef) => void;
}

export function DetailsPanel({
  node,
  detail,
  loading,
  error,
  onRetry,
  onClose,
  onShowImpact,
  onExpand,
  canSelect,
  onSelectRelated,
}: Props) {
  const [requestedView, setRequestedView] = useState<PanelView>("overview");
  const [copied, setCopied] = useState(false);
  const symbol = detail?.symbol ?? null;
  const location = symbol
    ? locationLabel(symbol.file_path, symbol.line_start, symbol.line_end)
    : repoRelativePath(node.publicId);
  const source = symbol?.source ?? null;
  const KindIcon = iconForKind(node.type);

  // Every node opens on its overview; the source is one click away.
  useEffect(() => {
    setRequestedView("overview");
    setCopied(false);
  }, [node.id]);
  // A node without source (or still loading) can only show the overview.
  const view: PanelView = requestedView === "source" && source ? "source" : "overview";

  async function copyLocation() {
    try {
      await navigator.clipboard.writeText(location);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be unavailable (insecure context, denied permission); nothing to recover.
    }
  }

  return (
    <aside
      aria-label="Node details"
      className="w-[380px] shrink-0 h-full overflow-y-auto border-l border-border bg-card/80 backdrop-blur-md text-xs flex flex-col"
    >
      <div className="flex flex-col gap-2 px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <Badge variant="outline" className={`w-fit gap-1 ${NODE_TEXT_CLASS[node.type]}`}>
            <KindIcon className="size-3" aria-hidden />
            {NODE_LABEL[node.type]}
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="size-6 cursor-pointer text-muted-foreground hover:text-foreground [&_svg]:size-3.5"
            aria-label="Close details"
          >
            <PanelRightClose />
          </Button>
        </div>

        <p className="font-mono font-semibold text-foreground text-base break-all">
          {symbol?.name ?? node.label}
        </p>

        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="min-w-0 truncate font-mono text-[11px]" title={location}>
            {shortPath(location)}
          </span>
          <button
            type="button"
            onClick={copyLocation}
            aria-label="Copy location"
            className="cursor-pointer shrink-0 hover:text-foreground"
          >
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          </button>
        </div>

        <PanelActions
          view={view}
          onViewChange={setRequestedView}
          hasSource={Boolean(source)}
          onImpact={() => onShowImpact(node)}
          onExpand={node.hasChildren ? () => onExpand(node) : undefined}
        />
      </div>

      {loading && <PanelSkeleton />}
      {error && (
        <div className="px-4 py-3">
          <InlineError
            title="Could not load details"
            message={error}
            action={<RetryButton onRetry={onRetry} />}
          />
        </div>
      )}
      {!loading && !error && !detail && (
        <p className="px-4 py-3 border-t border-border text-muted-foreground">
          No further details for this node.
        </p>
      )}

      {detail && symbol && (
        <>
          {view === "source" && source && (
            <div className="flex min-h-0 flex-1 flex-col border-t border-border">
              <SourceCode source={source} startLine={symbol.line_start ?? 1} className="min-h-0 flex-1" />
            </div>
          )}

          {view === "overview" && (
            <div className="border-t border-border">
              <Overview
                sections={sectionsFor(detail)}
                canSelect={canSelect}
                onSelect={onSelectRelated}
                truncated={detail.truncated}
                about={node.type === "File" ? undefined : { docstring: detail.docstring, chips: metaChips(detail) }}
              />
            </div>
          )}
        </>
      )}
    </aside>
  );
}

function PanelSkeleton() {
  return (
    <div className="px-4 py-3 border-t border-border flex flex-col gap-2" aria-busy>
      <Skeleton className="h-3 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

// The stored path may be absolute; the public id always carries the repo-relative one.
function repoRelativePath(publicId: string): string {
  return publicId.startsWith("file::") ? publicId.slice("file::".length) : publicId.split("::")[0];
}
