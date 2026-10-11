"use client";

import type { ReactNode } from "react";
import { Switch } from "@/components/ui/switch";

interface Props {
  /** Unique within the page; ties the label to its switch. */
  id: string;
  label: string;
  /** How many are on the globe right now. */
  count: number;
  /** How many exist in the index; shown as `count/total` when some are not on the globe yet. */
  total: number;
  enabled: boolean;
  onToggle: () => void;
  /** Colour key shown before the label: a dot for entities, a short line for relationships. */
  marker: ReactNode;
}

/** One graph filter: colour key, name, count and an on/off switch. Always shown, on or off. */
export function FilterRow({ id, label, count, total, enabled, onToggle, marker }: Props) {
  return (
    <div className="flex items-center gap-2 px-1.5 py-1">
      {marker}
      <label
        htmlFor={id}
        className={`flex-1 cursor-pointer select-none ${enabled ? "text-foreground" : "text-muted-foreground/60"}`}
      >
        {label}
      </label>
      <span
        className="font-mono tabular-nums text-muted-foreground"
        title={count === total ? `${total} in the index` : `${count} on the globe of ${total} in the index`}
      >
        {count === total ? total : `${count}/${total}`}
      </span>
      <Switch
        id={id}
        checked={enabled}
        onCheckedChange={onToggle}
        aria-label={`Show ${label}`}
        className="h-4 w-7 [&>span]:size-3 data-[state=checked]:[&>span]:translate-x-3"
      />
    </div>
  );
}
