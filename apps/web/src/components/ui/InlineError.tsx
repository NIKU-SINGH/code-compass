import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface InlineErrorProps {
  title: string;
  message: string;
  /** Optional call to action, typically a Retry button. */
  action?: ReactNode;
}

/** Generic inline error notice shared by data views. */
export function InlineError({ title, message, action }: InlineErrorProps) {
  return (
    <Alert variant="destructive">
      <CircleAlert className="size-4" aria-hidden />
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>{message}</AlertDescription>
        </div>
        {action}
      </div>
    </Alert>
  );
}
