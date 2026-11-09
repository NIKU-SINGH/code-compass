// Categorical colours come from the existing `--kind-*` / `--edge-*` theme tokens, in an order
// that was run through the data-viz palette validator for the neighbours that touch in a chart:
//
//   series (function, method, class, file)   adjacent CVD + normal-vision floor pass, light + dark
//
// The theme's colours are deliberately muted, so the validator's chroma-floor check still warns;
// every chart therefore also carries a legend, direct values, 2px gaps and a table view, and
// keeps these orders. Do not reorder them without re-running the validator.
export const SERIES_COLORS = [
  "var(--kind-function)",
  "var(--kind-method)",
  "var(--kind-class)",
  "var(--kind-file)",
] as const;

/** Single-series charts (one nominal measure) use one hue; labels carry identity. */
export const SINGLE_COLOR = "var(--kind-file)";

/** Remainder segments such as "in use" or "written by people". */
export const NEUTRAL_COLOR = "var(--muted-foreground)";
