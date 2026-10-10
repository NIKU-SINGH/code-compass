"use client";

import { useEffect, useState } from "react";
import { ApiError, searchSymbols, type SearchHit } from "@/lib/api";

const DEBOUNCE_MS = 200;
const RESULT_LIMIT = 12;

/** Debounced symbol search; superseded requests are aborted and ignored. */
export function useSymbolSearch(query: string): {
  results: ReadonlyArray<SearchHit>;
  loading: boolean;
  error: ApiError | null;
} {
  const [results, setResults] = useState<ReadonlyArray<SearchHit>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const trimmed = query.trim();

  useEffect(() => {
    if (trimmed.length < 1) {
      setResults([]);
      setError(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const timer = setTimeout(() => {
      searchSymbols(trimmed, { limit: RESULT_LIMIT, signal: controller.signal })
        .then((res) => {
          if (controller.signal.aborted) return;
          setResults(res.hits);
          setError(null);
          setLoading(false);
        })
        .catch((e: unknown) => {
          if (controller.signal.aborted) return;
          setError(e instanceof ApiError ? e : new ApiError("INTERNAL", "Search failed", 0));
          setResults([]);
          setLoading(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  return { results, loading, error };
}
