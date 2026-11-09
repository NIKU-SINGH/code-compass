import type { Via } from "@/lib/api";

/** Human-readable phrase for how an affected symbol reaches the target. */
export function viaText(via: Via | null): string {
  if (via === null) return "";
  const name = via.symbol.name;
  const kind = via.kind;
  switch (kind) {
    case "CALLS":
      return `calls ${name}`;
    case "CALLED_BY":
      return `called by ${name}`;
    case "IMPORTS":
      return `imports ${name}`;
    case "IMPORTED_BY":
      return `imported by ${name}`;
    case "INHERITS":
      return `inherits ${name}`;
    case "INHERITED_BY":
      return `inherited by ${name}`;
    case "OVERRIDES":
      return `overrides ${name}`;
    case "CONTAINED_IN":
      return `contained in ${name}`;
    default: {
      const unreachable: never = kind;
      return unreachable;
    }
  }
}
