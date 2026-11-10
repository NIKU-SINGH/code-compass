import type { Via } from "@/lib/api";

/** Human-readable phrase for how an affected symbol reaches the target. */
export function viaText(via: Via | null): string {
  if (via === null) return "";
  const name = via.symbol.name;
  const kind = via.kind;
  switch (kind) {
    case "CALLS":
      return `calls ${name}`;
    case "IMPORTS":
      return `imports ${name}`;
    case "INHERITS":
      return `inherits ${name}`;
    default: {
      const unreachable: never = kind;
      return unreachable;
    }
  }
}
