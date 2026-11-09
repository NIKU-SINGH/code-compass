"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getImpact,
  type AmbiguousReference,
  type ImpactResult,
  type SymbolNotFound,
} from "@/lib/api";

export type DependentsQueryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; result: ImpactResult }
  | { status: "ambiguous"; result: AmbiguousReference }
  | { status: "not_found"; result: SymbolNotFound }
  | { status: "error"; error: ApiError };

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  return new ApiError("INTERNAL", e instanceof Error ? e.message : "Unexpected error", 0);
}

interface QueryInputs {
  target: string | null;
  depth: number;
  attempt: number;
}

interface StoredState {
  inputs: QueryInputs;
  state: DependentsQueryState;
}

/**
 * Pure: a stored state is only exposed while it belongs to the current inputs;
 * otherwise (new target/depth/retry not yet settled) the view is loading, so a
 * stale result for another target is never rendered.
 */
export function deriveQueryState(stored: StoredState | null, current: QueryInputs): DependentsQueryState {
  if (current.target === null) return { status: "idle" };
  if (
    stored === null ||
    stored.inputs.target !== current.target ||
    stored.inputs.depth !== current.depth ||
    stored.inputs.attempt !== current.attempt
  ) {
    return { status: "loading" };
  }
  return stored.state;
}

/** Fetches impact for `target` at `depth`; each change aborts the in-flight request. */
export function useDependentsQuery(
  target: string | null,
  depth: number,
): DependentsQueryState & { retry: () => void } {
  const [stored, setStored] = useState<StoredState | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (target === null) return;
    const inputs: QueryInputs = { target, depth, attempt };
    const settle = (state: DependentsQueryState) => setStored({ inputs, state });
    const controller = new AbortController();
    getImpact(target, { depth, signal: controller.signal })
      .then((outcome) => {
        if (controller.signal.aborted) return;
        switch (outcome.status) {
          case "ok":
            return settle({ status: "ok", result: outcome.data });
          case "ambiguous":
            return settle({ status: "ambiguous", result: outcome.data });
          case "not_found":
            return settle({ status: "not_found", result: outcome.data });
        }
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        settle({ status: "error", error: toApiError(e) });
      });
    // Cleanup aborts on target/depth change and on unmount.
    return () => controller.abort();
  }, [target, depth, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...deriveQueryState(stored, { target, depth, attempt }), retry };
}
