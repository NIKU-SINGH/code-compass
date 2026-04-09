import type { ReactNode } from "react";

export default function ProjectLayout({ children }: { children: ReactNode }) {
  return <div className="h-svh overflow-hidden flex flex-col">{children}</div>;
}
