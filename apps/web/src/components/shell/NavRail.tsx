"use client";

import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { WorkspaceView } from "./useWorkspaceView";

export interface NavRailItem {
  id: WorkspaceView;
  label: string;
  icon: LucideIcon;
  shortcut?: string;
}

interface NavRailProps {
  items: ReadonlyArray<NavRailItem>;
  active: WorkspaceView;
  onSelect: (id: WorkspaceView) => void;
}

export function NavRail({ items, active, onSelect }: NavRailProps) {
  return (
    <TooltipProvider delayDuration={100}>
      <nav
        aria-label="Workspace views"
        className="flex w-14 flex-none flex-col items-center gap-1 border-r border-border bg-card py-2 text-sidebar-foreground"
      >
        {items.map(({ id, label, icon: Icon, shortcut }) => {
          const isActive = id === active;
          return (
            <Tooltip key={id}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={label}
                  aria-current={isActive ? "page" : undefined}
                  onClick={() => onSelect(id)}
                  className={cn(
                    "cursor-pointer",
                    isActive ? "bg-accent text-primary" : "text-muted-foreground",
                  )}
                >
                  <Icon className="size-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right" className="flex items-center gap-2">
                {label}
                {shortcut && <span className="font-mono text-xs text-muted-foreground">{shortcut}</span>}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>
    </TooltipProvider>
  );
}
