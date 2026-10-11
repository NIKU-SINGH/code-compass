"use client";

import { useCallback, useEffect, useState } from "react";
import { getNodeDetail, isAbortError, type NodeDetail } from "@/lib/api";

interface State {
  detail: NodeDetail | null;
  loading: boolean;
  error: string | null;
}

const IDLE: State = { detail: null, loading: false, error: null };

/**
 * Loads the details of the node with public id `ref`; pass `null` for no selection.
 * A change of `ref` cancels the request still in flight, and `retry` re-runs a failed one.
 * `detail` stays `null` when the backend has nothing for the node.
 */
export function useNodeDetail(ref: string | null) {
  const [state, setState] = useState<State>(IDLE);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!ref) {
      setState(IDLE);
      return;
    }
    const controller = new AbortController();
    setState({ detail: null, loading: true, error: null });
    getNodeDetail(ref, { signal: controller.signal })
      .then((detail) => setState({ detail, loading: false, error: null }))
      .catch((e: unknown) => {
        if (isAbortError(e) || controller.signal.aborted) return;
        setState({
          detail: null,
          loading: false,
          error: e instanceof Error ? e.message : "Could not load details",
        });
      });
    return () => controller.abort();
  }, [ref, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, retry };
}
