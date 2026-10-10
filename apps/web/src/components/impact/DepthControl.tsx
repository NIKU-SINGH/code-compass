import { Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DepthControlProps {
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}

export function DepthControl({ value, min, max, onChange }: DepthControlProps) {
  return (
    <div role="group" aria-label="Depth" className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">Depth</span>
      <div className="flex items-center rounded-md border border-border bg-muted p-0.5">
        <Button
          variant="ghost"
          size="icon"
          className="size-6 cursor-pointer"
          aria-label="Decrease depth"
          disabled={value <= min}
          onClick={() => onChange(value - 1)}
        >
          <Minus className="size-3.5" />
        </Button>
        <span className="w-7 text-center font-mono text-xs" aria-live="polite">
          {value}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="size-6 cursor-pointer"
          aria-label="Increase depth"
          disabled={value >= max}
          onClick={() => onChange(value + 1)}
        >
          <Plus className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
