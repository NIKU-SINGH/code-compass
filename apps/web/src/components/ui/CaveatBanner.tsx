import { RefreshCw, TriangleAlert, type LucideIcon } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Caveat, CaveatCode } from "@/lib/api";

const CAVEAT_ICONS: Record<CaveatCode, LucideIcon> = {
  UNRESOLVED_CALLS: TriangleAlert,
  STALE_INDEX: RefreshCw,
};

const WARNING_CAVEATS: ReadonlySet<CaveatCode> = new Set(["UNRESOLVED_CALLS", "STALE_INDEX"]);

export function CaveatBanner({ caveat }: { caveat: Caveat }) {
  const Icon = CAVEAT_ICONS[caveat.code];
  return (
    <Alert variant={WARNING_CAVEATS.has(caveat.code) ? "warning" : "default"} role="status" className="py-2.5">
      <Icon className="size-4" aria-hidden />
      <AlertDescription>{caveat.message}</AlertDescription>
    </Alert>
  );
}
