const SCHEME_QUERY = "(prefers-color-scheme: dark)";
const FALLBACK_TOKEN = "--muted-foreground";
// Only reached when even the fallback token cannot be resolved (no DOM, no canvas, broken theme).
const LAST_RESORT = "#808080";

let cache = new Map<string, string>();
let schemeVersion = 0;
let swatch: CanvasRenderingContext2D | null = null;
const listeners = new Set<() => void>();
let media: MediaQueryList | null = null;

/** Cache key: the colour depends on the active scheme, so a stale entry can never leak across schemes. */
export function colorCacheKey(dark: boolean, varName: string): string {
  return `${dark ? "dark" : "light"}:${varName}`;
}

function isDark(): boolean {
  return window.matchMedia(SCHEME_QUERY).matches;
}

function handleSchemeChange() {
  cache = new Map();
  schemeVersion += 1;
  listeners.forEach((l) => l());
}

/** Increments once per OS colour-scheme change observed while anything was subscribed. */
export function getColorSchemeVersion(): number {
  return schemeVersion;
}

function getSwatch(): CanvasRenderingContext2D | null {
  if (swatch) return swatch;
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  swatch = canvas.getContext("2d", { willReadFrequently: true });
  return swatch;
}

function toHex(n: number): string {
  return n.toString(16).padStart(2, "0");
}

/**
 * Resolves a CSS custom property (e.g. `--kind-file`) to `#rrggbb`.
 *
 * THREE.js cannot parse `oklch()` or `color-mix()`, which the theme tokens use, so the
 * browser's own parser is borrowed: the colour is painted onto a 1x1 canvas and read back.
 * Results are cached until the OS colour scheme changes. Falls back to mid-grey when the
 * variable is missing, unparsable, or no DOM is available (SSR).
 */
export function resolveCssColor(varName: string): string {
  if (typeof document === "undefined") return LAST_RESORT;
  const key = colorCacheKey(isDark(), varName);
  const hit = cache.get(key);
  if (hit) return hit;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  const ctx = getSwatch();
  let hex: string | null = null;
  if (raw && ctx) {
    // An unparsable value leaves fillStyle untouched, so prime it with two different
    // sentinels and only trust the result when both runs agree.
    const read = (sentinel: string) => {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = sentinel;
      ctx.fillStyle = raw;
      ctx.fillRect(0, 0, 1, 1);
      return ctx.getImageData(0, 0, 1, 1).data;
    };
    const a = read("#000000");
    const b = read("#ffffff");
    // The alpha channel is discarded: the colour tokens used by the graph are opaque.
    if (a[3] > 0 && a[0] === b[0] && a[1] === b[1] && a[2] === b[2]) {
      hex = `#${toHex(a[0])}${toHex(a[1])}${toHex(a[2])}`;
    }
  }
  if (hex === null) {
    // Not cached: the failure may be transient (e.g. stylesheet not applied yet).
    return varName === FALLBACK_TOKEN ? LAST_RESORT : resolveCssColor(FALLBACK_TOKEN);
  }
  cache.set(key, hex);
  return hex;
}

/** Subscribes to OS colour-scheme changes (cache is already invalidated when `listener` runs). */
export function onColorSchemeChange(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  if (listeners.size === 0) {
    // Nothing was watching while unsubscribed, so anything cached may predate a scheme flip.
    cache = new Map();
    media = window.matchMedia(SCHEME_QUERY);
    media.addEventListener("change", handleSchemeChange);
  }
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && media) {
      media.removeEventListener("change", handleSchemeChange);
      media = null;
    }
  };
}
