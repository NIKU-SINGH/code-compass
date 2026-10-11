"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { otherTheme } from "./theme";
import { useTheme } from "./useTheme";

/** Switches between the light and dark theme; shows the one it would switch to. */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const target = otherTheme(theme);
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={`Switch to ${target} theme`}
      title={`Switch to ${target} theme`}
      className="cursor-pointer text-muted-foreground hover:text-foreground"
    >
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}
