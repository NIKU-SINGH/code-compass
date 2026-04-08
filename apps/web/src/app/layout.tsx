import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { MainLayout } from "@/components/layout/MainLayout";

export const metadata: Metadata = {
  title: "Code Compass",
  description: "Navigate your codebase with AI",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full">
        <MainLayout>{children}</MainLayout>
      </body>
    </html>
  );
}
