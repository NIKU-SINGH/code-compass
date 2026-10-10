import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { ActiveView } from "@/components/workspace/ActiveView";

export default function HomePage() {
  return (
    <div className="flex-1 flex overflow-hidden">
      <Suspense fallback={<Skeleton className="flex-1 rounded-none" />}>
        <ActiveView />
      </Suspense>
    </div>
  );
}
