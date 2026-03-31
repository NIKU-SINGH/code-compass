import { ChevronDown, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";

const SELECTORS = [
  { label: "Claude 3.5", dropdown: true },
  { label: "Auto", dropdown: true },
  { label: "Chat", dropdown: false },
  { label: "Full access", dropdown: false },
];

export function PromptCard() {
  return (
    <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-4">
      <Textarea
        rows={4}
        placeholder="Ask anything, @tag files/folders or use #model"
        className="border-none shadow-none resize-none overflow-hidden bg-transparent p-0 text-sm min-h-0 focus-visible:ring-0 placeholder:text-muted-foreground"
        style={{ fontFamily: "inherit" }}
      />

      <Separator />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {SELECTORS.map((s) => (
            <Button
              key={s.label}
              variant="ghost"
              size="sm"
              className="h-auto px-0 py-0 text-xs text-muted-foreground hover:text-foreground hover:bg-transparent gap-0.5"
            >
              {s.label}
              {s.dropdown && <ChevronDown className="!size-3" />}
            </Button>
          ))}
        </div>

        <Button
          size="icon"
          variant="destructive"
          className="rounded-full size-8 shrink-0"
        >
          <Square className="!size-3.5 fill-current" />
        </Button>
      </div>
    </div>
  );
}
