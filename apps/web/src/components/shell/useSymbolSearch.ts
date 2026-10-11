"use client";

import { useEffect, useState } from "react";
import { isAbortError, searchSymbols, type SearchHit } from "@/lib/api";

const DEBOUNCE_MS = 180;
const LIMIT = 20;

export interface SymbolSearch {
  hits: ReadonlyArray<SearchHit>;
  loading: boolean;
  error: boolean;
}

/**
 * Searches files, classes and functions as the user types. Waits briefly after each keystroke,
 * cancels the request a newer query makes obsolete, and returns nothing for a blank query.
 */
export function useSymbolSearch(query: string): SymbolSearch {
  const [state, setState] = useState<SymbolSearch>({ hits: [], loading: false, error: false });
  const text = query.trim();

  useEffect(() => {
    if (!text) {
      setState({ hits: [], loading: false, error: false });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: false }));
    const timer = setTimeout(() => {
      searchSymbols(text, { limit: LIMIT, signal: controller.signal })
        .then((r) => setState({ hits: r.hits, loading: false, error: false }))
        .catch((e: unknown) => {
          if (isAbortError(e) || controller.signal.aborted) return;
          setState({ hits: [], loading: false, error: true });
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [text]);

  return state;
}
