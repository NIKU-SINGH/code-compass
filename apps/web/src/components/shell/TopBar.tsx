"use client";

import { useEffect, useState } from "react";
import { Clock, Compass, Search } from "lucide-react";
import { relativeTime } from "@/components/overview/insightCards";
import { Skeleton } from "@/components/ui/skeleton";
import { SearchPalette } from "./SearchPalette";
import { ThemeToggle } from "./ThemeToggle";
import { repoName, useIndexStatus } from "./useIndexStatus";
import { useWorkspaceView } from "./useWorkspaceView";

/** `⌘` on Apple platforms, `Ctrl` elsewhere; known only on the client. */
function useModifierLabel(): string {
  const [label, setLabel] = useState("Ctrl");
  useEffect(() => {
    if (/Mac|iPhone|iPad/.test(navigator.platform)) setLabel("⌘");
  }, []);
  return label;
}

/** Repository identity, a search that opens the command palette (⌘K), and the theme toggle. */
export function TopBar() {
  const status = useIndexStatus();
  const { setView } = useWorkspaceView();
  const [searchOpen, setSearchOpen] = useState(false);
  const modifier = useModifierLabel();

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <header className="grid h-12 flex-none grid-cols-[1fr_minmax(0,32rem)_1fr] items-center gap-3 border-b border-border bg-card px-3">
      <div className="flex min-w-0 items-center gap-2.5">
        <span className="flex size-7 flex-none items-center justify-center rounded-md border border-primary/60 text-primary">
          <Compass className="size-4" aria-hidden />
        </span>
        {status ? (
          <>
            <span className="truncate text-sm font-semibold" title={status.repo_root}>
              {repoName(status.repo_root)}
            </span>
            <span className="hidden items-center gap-1 whitespace-nowrap text-xs text-muted-foreground sm:flex">
              <Clock className="size-3" aria-hidden />
              indexed {relativeTime(new Date(status.indexed_at), new Date())}
            </span>
          </>
        ) : (
          <Skeleton className="h-4 w-28" />
        )}
      </div>

      <button
        type="button"
        onClick={() => setSearchOpen(true)}
        aria-label="Search files, classes, functions"
        className="flex h-8 w-full cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-3 text-left text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Search className="size-3.5 flex-none" aria-hidden />
        <span className="flex-1 truncate">Search files, classes, functions…</span>
        <kbd className="flex items-center gap-1 font-mono text-[10px]">
          <span className="rounded border border-border bg-muted px-1.5 py-0.5">{modifier}</span>
          <span className="rounded border border-border bg-muted px-1.5 py-0.5">K</span>
        </kbd>
      </button>

      <div className="flex items-center justify-end gap-1">
        <ThemeToggle />
      </div>

      <SearchPalette
        open={searchOpen}
        onOpenChange={setSearchOpen}
        onSelect={(symbol) => setView("graph", symbol.id)}
      />
    </header>
  );
}
