export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "compass-theme";

/** The stored preference, or `null` when absent or not a theme (then the OS decides). */
export function parseStoredTheme(raw: string | null): Theme | null {
  return raw === "light" || raw === "dark" ? raw : null;
}

/** An explicit choice wins; otherwise follow the OS. */
export function resolveTheme(stored: Theme | null, systemDark: boolean): Theme {
  return stored ?? (systemDark ? "dark" : "light");
}

export function otherTheme(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark";
}

/**
 * Inline script for `<head>`: sets `<html data-theme>` before first paint so the page never flashes
 * the wrong scheme. It mirrors `resolveTheme`; storage can be blocked, so it falls back to light.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var s=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY
)});var t=s==="light"||s==="dark"?s:(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme="light"}})();`;
