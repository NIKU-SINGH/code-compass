"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { SidebarInset } from "@/components/ui/sidebar";

export function LayoutShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const fullHeight = pathname.startsWith("/project/");

  return (
    <SidebarInset
      className={[
        "flex-1 min-w-0 flex flex-col",
        fullHeight ? "h-svh overflow-hidden" : "overflow-y-auto",
      ].join(" ")}
    >
      {children}
    </SidebarInset>
  );
}
