"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export type WorkspaceView = "overview" | "graph" | "impact";

export const WORKSPACE_VIEWS: ReadonlyArray<WorkspaceView> = ["overview", "graph", "impact"];

function parseView(raw: string | null): WorkspaceView {
  if (raw === "explore") return "graph";
  return WORKSPACE_VIEWS.find((v) => v === raw) ?? "overview";
}

/** Reads and writes the active workspace view from `?view=` and `?focus=`. */
export function useWorkspaceView(): {
  view: WorkspaceView;
  focus: string | null;
  setView: (view: WorkspaceView, focus?: string | null) => void;
} {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const setView = useCallback(
    (next: WorkspaceView, nextFocus?: string | null) => {
      const query = new URLSearchParams({ view: next });
      if (nextFocus) query.set("focus", nextFocus);
      router.replace(`${pathname}?${query.toString()}`, { scroll: false });
    },
    [router, pathname],
  );

  return { view: parseView(params.get("view")), focus: params.get("focus"), setView };
}
