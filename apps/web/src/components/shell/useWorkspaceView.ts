"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export type WorkspaceView = "overview" | "graph" | "impact";

export const WORKSPACE_VIEWS: ReadonlyArray<WorkspaceView> = ["overview", "graph", "impact"];

function parseView(raw: string | null): WorkspaceView {
  if (raw === "explore") return "graph";
  return WORKSPACE_VIEWS.find((v) => v === raw) ?? "overview";
}

/** Reads the active workspace view from `?view=` and `?focus=`; `setView` pushes a history entry. */
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
      // Every caller is a user navigation, so it gets a history entry (Back works);
      // re-selecting the current view and focus adds none.
      if (query.toString() === params.toString()) return;
      router.push(`${pathname}?${query.toString()}`, { scroll: false });
    },
    [router, pathname, params],
  );

  return { view: parseView(params.get("view")), focus: params.get("focus"), setView };
}
