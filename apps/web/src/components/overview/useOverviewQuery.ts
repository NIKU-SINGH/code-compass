"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getOverview, type OverviewResult } from "@/lib/api";

export type OverviewQueryState =
  | { status: "loading" }
  | { status: "ok"; result: OverviewResult }
  | { status: "error"; error: ApiError };

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  return new ApiError("INTERNAL", e instanceof Error ? e.message : "Unexpected error", 0);
}

interface StoredState {
  attempt: number;
  state: OverviewQueryState;
}

/** Pure: a stored state only counts while it belongs to the current attempt; otherwise loading. */
export function deriveOverviewState(stored: StoredState | null, attempt: number): OverviewQueryState {
  return stored !== null && stored.attempt === attempt ? stored.state : { status: "loading" };
}

/** Fetches the index overview; retry() re-fetches and aborts any in-flight request. */
export function useOverviewQuery(): OverviewQueryState & { retry: () => void } {
  const [stored, setStored] = useState<StoredState | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const settle = (state: OverviewQueryState) => setStored({ attempt, state });
    getOverview({ signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        settle({ status: "ok", result });
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        settle({ status: "error", error: toApiError(e) });
      });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...deriveOverviewState(stored, attempt), retry };
}
