import type { ReactNode } from "react";
import { SidebarInset } from "@/components/ui/sidebar";

export function LayoutShell({ children }: { children: ReactNode }) {
  return (
    <SidebarInset className="flex-1 min-w-0 flex flex-col overflow-y-auto">
      {children}
    </SidebarInset>
  );
}
