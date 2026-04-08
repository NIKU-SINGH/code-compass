import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@/styles/globals.css";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { LayoutShell } from "./_shell";

export const metadata: Metadata = {
  title: "Code Compass",
  description: "Navigate your codebase with AI",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full">
        <SidebarProvider>
          <AppSidebar />
          <LayoutShell>{children}</LayoutShell>
        </SidebarProvider>
      </body>
    </html>
  );
}
