"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { components } from "@/lib/api-types";

export type IndexStatus = components["schemas"]["IndexStatus"];

/** The index's repository and build time, for the top bar; `null` until loaded or when unavailable. */
export function useIndexStatus(): IndexStatus | null {
  const [status, setStatus] = useState<IndexStatus | null>(null);
  useEffect(() => {
    let cancelled = false;
    apiFetch<IndexStatus>("/api/status")
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch(() => {
        // The bar still works without it; it just shows no repository name.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return status;
}

/** Last path segment of a repository root: `/Users/me/code/ledger-api` -> `ledger-api`. */
export function repoName(repoRoot: string): string {
  const parts = repoRoot.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? repoRoot;
}
