"use client";

import { useEffect } from "react";
import type { WorkspaceView } from "./useWorkspaceView";

const CHORD_WINDOW_MS = 1000;

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** Switches view on a `g` then key chord, e.g. `{ o: "overview" }`. */
export function useViewShortcuts(
  keys: Readonly<Record<string, WorkspaceView>>,
  onSelect: (view: WorkspaceView) => void,
): void {
  useEffect(() => {
    let armedAt = 0;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.repeat || e.isComposing || e.shiftKey || e.metaKey || e.ctrlKey || e.altKey || isEditable(e.target)) return;
      const key = e.key.toLowerCase();
      const armed = Date.now() - armedAt <= CHORD_WINDOW_MS;
      const view = keys[key];
      if (armed && view) {
        onSelect(view);
        armedAt = 0;
      } else {
        armedAt = key === "g" ? Date.now() : 0;
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [keys, onSelect]);
}
