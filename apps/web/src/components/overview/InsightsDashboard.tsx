"use client";

import { RetryButton } from "@/components/ui/RetryButton";
import { CaveatBanner } from "@/components/ui/CaveatBanner";
import { InlineError } from "@/components/ui/InlineError";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewResult } from "@/lib/api";
import { errorCopy } from "@/lib/errorCopy";
import { GraphComposition } from "./GraphComposition";
import { IndexHealth } from "./IndexHealth";
import {
  compositionEdges,
  compositionSegments,
  freshnessText,
  statTiles,
  totalEdges,
} from "./insightCards";
import { healthIssues, resolvedCallPercent } from "./signals/cards";
import { SAMPLE_INDEX_HEALTH } from "./signals/sampleData";
import { SignalSections } from "./signals/SignalSections";
import { StatTile } from "./StatTile";
import { useInsightsQuery } from "./useInsightsQuery";

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
  const query = useInsightsQuery();

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
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.7fr_1fr]">
        <GraphComposition
          nodeCount={r.counts.files + r.counts.classes + r.counts.functions}
          edgeCount={totalEdges(r.counts)}
          segments={compositionSegments(r.counts)}
          edges={compositionEdges(r.counts)}
        />
        <IndexHealth
          resolvedPercent={resolvedCallPercent(SAMPLE_INDEX_HEALTH)}
          issues={healthIssues(SAMPLE_INDEX_HEALTH)}
          note="Unresolved calls are missing from Impact results, so a change may reach further than shown."
          badge="Sample data"
          badgeTitle="Placeholder numbers: the index does not record this yet"
        />
      </div>
      <SignalSections />
    </>
  );

  const failure = query.status === "error" ? errorCopy(query.error) : null;

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-8 pb-14 pt-6">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground">What is in this index, and how healthy the code is.</p>
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
