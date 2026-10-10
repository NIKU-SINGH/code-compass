"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getImpact,
  type AmbiguousReference,
  type ImpactResult,
  type SymbolNotFound,
} from "@/lib/api";

export type ImpactQueryState =
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

/** Fetches impact for `target` at `depth`; each change aborts the in-flight request. */
export function useImpactQuery(
  target: string | null,
  depth: number,
): ImpactQueryState & { retry: () => void } {
  const [state, setState] = useState<ImpactQueryState>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (target === null) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });
    getImpact(target, { depth, signal: controller.signal })
      .then((outcome) => {
        if (controller.signal.aborted) return;
        switch (outcome.status) {
          case "ok":
            return setState({ status: "ok", result: outcome.data });
          case "ambiguous":
            return setState({ status: "ambiguous", result: outcome.data });
          case "not_found":
            return setState({ status: "not_found", result: outcome.data });
        }
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setState({ status: "error", error: toApiError(e) });
      });
    // Cleanup aborts on target/depth change and on unmount.
    return () => controller.abort();
  }, [target, depth, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}
