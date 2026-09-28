import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Code Compass",
  description: "Visualize your codebase as a knowledge graph",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-svh overflow-hidden flex flex-col">{children}</body>
    </html>
  );
}
