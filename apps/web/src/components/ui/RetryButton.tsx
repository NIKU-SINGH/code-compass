import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface RetryButtonProps {
  onRetry: () => void;
  label?: string;
}

/** Outline "Retry" action for inline error notices. */
export function RetryButton({ onRetry, label = "Retry" }: RetryButtonProps) {
  return (
    <Button variant="outline" size="sm" className="cursor-pointer" onClick={onRetry}>
      <RefreshCw className="size-3.5" aria-hidden />
      {label}
    </Button>
  );
}
