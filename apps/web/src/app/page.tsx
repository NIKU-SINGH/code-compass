import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { TopBar } from "@/components/shell/TopBar";
import { ActiveView } from "@/components/workspace/ActiveView";

export default function HomePage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <Suspense fallback={<div className="h-12 flex-none border-b border-border bg-card" />}>
        <TopBar />
      </Suspense>
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Suspense fallback={<Skeleton className="flex-1 rounded-none" />}>
          <ActiveView />
        </Suspense>
      </div>
    </div>
  );
}
