"use client";

import { RetryButton } from "@/components/ui/RetryButton";
import { CaveatBanner } from "@/components/ui/CaveatBanner";
import { InlineError } from "@/components/ui/InlineError";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewResult } from "@/lib/api";
import { errorCopy } from "@/lib/errorCopy";
import { GraphComposition } from "./GraphComposition";
import { IndexHealth } from "./IndexHealth";
import { IndexStatus } from "./IndexStatus";
import {
  compositionEdges,
  compositionSegments,
  indexFreshness,
  statTiles,
  totalEdges,
} from "./insightCards";
import { healthIssues, resolvedCallPercent } from "./signals/cards";
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
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {statTiles(r.counts).map((t) => (
          <StatTile key={t.id} label={t.label} value={t.value} detail={t.detail} colorClass={t.colorClass} />
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
          resolvedPercent={resolvedCallPercent(r.call_resolution)}
          issues={healthIssues(r.call_resolution)}
          note="Unresolved calls are missing from Impact results, so a change may reach further than shown."
        />
      </div>
      <SignalSections />
    </>
  );

  const failure = query.status === "error" ? errorCopy(query.error) : null;

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 px-8 pb-14 pt-6">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
            <p className="text-sm text-muted-foreground">What is in this index, and how healthy the code is.</p>
          </div>
          {query.status === "ok" && (
            <IndexStatus {...indexFreshness(query.result.index)} repoRoot={query.result.index.repo_root} />
          )}
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
