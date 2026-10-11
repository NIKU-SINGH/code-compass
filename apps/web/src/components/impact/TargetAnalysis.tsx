"use client";

import { useState } from "react";
import { CaveatBanner } from "@/components/ui/CaveatBanner";
import { InlineError } from "@/components/ui/InlineError";
import { RetryButton } from "@/components/ui/RetryButton";
import { useWorkspaceView } from "@/components/shell/useWorkspaceView";
import type { ImpactGroup } from "@/lib/api";
import { DEFAULT_IMPACT_DEPTH, MAX_DEPTH } from "@/lib/limits";
import { AffectedGroupList } from "./AffectedGroupList";
import { DepthControl } from "./DepthControl";
import { errorCopy } from "@/lib/errorCopy";
import {
  AmbiguousChooser,
  EmptyResult,
  IdleHint,
  LoadingRows,
  NotFoundHint,
} from "./ResultStates";
import { TargetCard } from "./TargetCard";
import { TargetPicker } from "./TargetPicker";
import { useDependentsQuery } from "./useDependentsQuery";
import { useSymbolSearch } from "./useSymbolSearch";

export function TargetAnalysis() {
  const { focus: rawFocus, setView } = useWorkspaceView();
  const focus = rawFocus?.trim() || null;
  const [depth, setDepth] = useState(DEFAULT_IMPACT_DEPTH);
  const [query, setQuery] = useState("");
  const search = useSymbolSearch(query);
  const state = useDependentsQuery(focus, depth);

  const retarget = (id: string) => setView("impact", id);
  const pick = (symbol: { id: string }) => {
    setQuery("");
    retarget(symbol.id);
  };

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-8 pb-14 pt-6">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold tracking-tight">Impact</h1>
          <p className="text-sm text-muted-foreground">If I change this, what else is affected?</p>
        </div>

        <TargetPicker
          query={query}
          onQueryChange={setQuery}
          results={search.results}
          loading={search.loading}
          error={search.error}
          onPick={pick}
          autoFocus={focus === null}
        />

        {focus !== null && (
          <div className="flex justify-end">
            <DepthControl value={depth} min={1} max={MAX_DEPTH} onChange={setDepth} />
          </div>
        )}

        <div aria-live="polite" className="flex flex-col gap-4">
          {state.status === "idle" && <IdleHint />}
          {state.status === "loading" && <LoadingRows />}
          {state.status === "ambiguous" && (
            <AmbiguousChooser reference={state.result.reference} candidates={state.result.candidates} onChoose={pick} />
          )}
          {state.status === "not_found" && (
            <NotFoundHint reference={state.result.reference} suggestions={state.result.suggestions} onChoose={pick} />
          )}
          {state.status === "error" && <ErrorNotice state={state} />}
          {state.status === "ok" && (
            <>
              <TargetCard result={state.result} onShowInGraph={(id) => setView("graph", id)} />
              {state.result.truncated && (
                <p className="text-xs text-muted-foreground">
                  Showing the first {shownCount(state.result.groups)} of {state.result.total}
                </p>
              )}
              {state.result.caveats.map((c) => (
                <CaveatBanner key={c.code} caveat={c} />
              ))}
              {state.result.groups.length === 0 ? (
                <EmptyResult
                  maybeIncomplete={state.result.caveats.some((c) => c.code === "UNRESOLVED_CALLS")}
                />
              ) : (
                <AffectedGroupList groups={state.result.groups} onRetarget={retarget} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function shownCount(groups: ReadonlyArray<ImpactGroup>): number {
  return groups.reduce((n, g) => n + g.items.length, 0);
}

function ErrorNotice({ state }: { state: Extract<ReturnType<typeof useDependentsQuery>, { status: "error" }> }) {
  const copy = errorCopy(state.error);
  return (
    <InlineError
      title={copy.title}
      message={copy.message}
      action={copy.retryable ? <RetryButton onRetry={state.retry} /> : undefined}
    />
  );
}
