"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { onColorSchemeChange } from "@/lib/cssColor";
import { THEME_STORAGE_KEY, otherTheme, parseStoredTheme, resolveTheme, type Theme } from "./theme";

function readStored(): Theme | null {
  try {
    return parseStoredTheme(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return null;
  }
}

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/**
 * The active theme and a toggle. The choice is stored and applied to `<html data-theme>`; until the
 * user makes one, the page follows the OS and tracks changes to it.
 */
export function useTheme(): { theme: Theme; toggle: () => void } {
  // The server can't know the theme, so it renders light; React re-reads the attribute right after
  // hydration (and on every change), which avoids a markup mismatch.
  const theme = useSyncExternalStore(onColorSchemeChange, currentTheme, () => "light" as Theme);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => {
      if (readStored() === null) {
        document.documentElement.dataset.theme = resolveTheme(null, media.matches);
      }
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);

  const toggle = useCallback(() => {
    const next = otherTheme(currentTheme());
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage can be blocked (private window); the choice still applies for this session.
    }
  }, []);

  return { theme, toggle };
}
