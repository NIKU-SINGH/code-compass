"use client";

import { RetryButton } from "@/components/impact/ResultStates";
import { useWorkspaceView } from "@/components/shell/useWorkspaceView";
import { CaveatBanner } from "@/components/ui/CaveatBanner";
import { InlineError } from "@/components/ui/InlineError";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewResult } from "@/lib/api";
import { errorCopy } from "@/lib/errorCopy";
import { BreakdownBar } from "./BreakdownBar";
import { InsightCard } from "./InsightCard";
import { InsightGroup } from "./InsightGroup";
import {
  edgeBreakdown,
  freshnessText,
  kindBreakdown,
  librariesCard,
  mostCalledCard,
  mostImportedCard,
  riskiestCard,
  statTiles,
  type InsightCardData,
} from "./insightCards";
import { StatTile } from "./StatTile";
import { useOverviewQuery } from "./useOverviewQuery";

function LoadingState() {
  return (
    <div role="status" aria-label="Loading overview" className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Skeleton className="h-56" />
        <Skeleton className="h-56" />
      </div>
    </div>
  );
}

export function InsightsDashboard() {
  const query = useOverviewQuery();
  const { setView } = useWorkspaceView();

  const renderCard = (card: InsightCardData) => {
    const target = card.navigateTo;
    return (
      <InsightCard
        key={card.id}
        title={card.title}
        description={card.description}
        icon={card.icon}
        rows={card.rows}
        emptyText={card.emptyText}
        onSelect={target ? (row) => setView(target, row.id) : undefined}
      />
    );
  };

  const renderResult = (r: OverviewResult) => (
    <>
      {r.caveats.length > 0 && (
        <div className="flex flex-col gap-2">
          {r.caveats.map((c) => (
            <CaveatBanner key={c.code} caveat={c} />
          ))}
        </div>
      )}
      <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
        <span>{freshnessText(r.index)}</span>
        <span className="truncate font-mono">{r.index.repo_root}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {statTiles(r.counts).map((t) => (
          <StatTile key={t.id} label={t.label} value={t.value} icon={t.icon} />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BreakdownBar title="Entities by kind" segments={kindBreakdown(r.counts)} />
        <BreakdownBar title="Edges by type" segments={edgeBreakdown(r.counts)} />
      </div>
      <InsightGroup title="Impact">
        {renderCard(riskiestCard(r))}
        {renderCard(mostImportedCard(r))}
      </InsightGroup>
      <InsightGroup title="Usage">
        {renderCard(mostCalledCard(r))}
        {renderCard(librariesCard(r))}
      </InsightGroup>
    </>
  );

  const failure = query.status === "error" ? errorCopy(query.error) : null;

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-8 pb-14 pt-6">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground">What is in this index, and where the risk sits.</p>
        </div>
        {query.status === "loading" && <LoadingState />}
        {failure && (
          <InlineError
            title={failure.title}
            message={failure.message}
            action={failure.retryable ? <RetryButton onRetry={query.retry} /> : undefined}
          />
        )}
        {query.status === "ok" && renderResult(query.result)}
      </div>
    </div>
  );
}
