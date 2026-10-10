const SCHEME_QUERY = "(prefers-color-scheme: dark)";
const FALLBACK = "#888888";

let cache = new Map<string, string>();
let swatch: CanvasRenderingContext2D | null = null;
const listeners = new Set<() => void>();
let media: MediaQueryList | null = null;

function handleSchemeChange() {
  cache = new Map();
  listeners.forEach((l) => l());
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
  if (typeof document === "undefined") return FALLBACK;
  const hit = cache.get(varName);
  if (hit) return hit;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  const ctx = getSwatch();
  let hex = FALLBACK;
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
    if (a[3] > 0 && a[0] === b[0] && a[1] === b[1] && a[2] === b[2]) {
      hex = `#${toHex(a[0])}${toHex(a[1])}${toHex(a[2])}`;
    }
  }
  cache.set(varName, hex);
  return hex;
}

/** Subscribes to OS colour-scheme changes (cache is already invalidated when `listener` runs). */
export function onColorSchemeChange(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  if (listeners.size === 0) {
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
