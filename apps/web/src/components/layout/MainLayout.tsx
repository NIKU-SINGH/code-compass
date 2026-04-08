"use client";

import { usePathname } from "next/navigation";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "./Sidebar";

export function MainLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const fullHeight = pathname.startsWith("/project/");

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset
        className={[
          "flex-1 min-w-0 flex flex-col",
          fullHeight ? "h-svh overflow-hidden" : "overflow-y-auto",
        ].join(" ")}
      >
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
