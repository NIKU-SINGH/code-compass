import type { PrismTheme } from "prism-react-renderer";

// Syntax colours come from the existing theme tokens, so the code block follows light/dark
// with everything else instead of carrying a palette of its own.
export const sourceTheme: PrismTheme = {
  plain: { color: "var(--foreground)", backgroundColor: "transparent" },
  styles: [
    { types: ["keyword", "boolean", "builtin", "important"], style: { color: "var(--kind-method)" } },
    {
      types: ["string", "triple-quoted-string", "string-interpolation", "char"],
      style: { color: "var(--kind-external)" },
    },
    { types: ["function", "class-name"], style: { color: "var(--kind-file)" } },
    { types: ["number", "constant"], style: { color: "var(--kind-function)" } },
    { types: ["decorator", "annotation", "attr-name"], style: { color: "var(--kind-class)" } },
    { types: ["comment"], style: { color: "var(--muted-foreground)", fontStyle: "italic" } },
    { types: ["punctuation", "operator"], style: { color: "var(--muted-foreground)" } },
  ],
};
