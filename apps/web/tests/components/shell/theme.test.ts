import { describe, expect, it } from "vitest";
import {
  THEME_INIT_SCRIPT,
  THEME_STORAGE_KEY,
  otherTheme,
  parseStoredTheme,
  resolveTheme,
} from "@/components/shell/theme";

describe("theme resolution", () => {
  it("accepts only the two themes from storage", () => {
    expect(parseStoredTheme("dark")).toBe("dark");
    expect(parseStoredTheme("light")).toBe("light");
    expect(parseStoredTheme("system")).toBeNull();
    expect(parseStoredTheme(null)).toBeNull();
  });

  it("lets an explicit choice beat the OS, and follows the OS otherwise", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme(null, false)).toBe("light");
  });

  it("flips between the two", () => {
    expect(otherTheme("dark")).toBe("light");
    expect(otherTheme("light")).toBe("dark");
  });
});

describe("pre-paint script", () => {
  it("reads the same storage key the hook writes and sets the attribute the CSS reads", () => {
    expect(THEME_INIT_SCRIPT).toContain(`"${THEME_STORAGE_KEY}"`);
    expect(THEME_INIT_SCRIPT).toContain("dataset.theme");
  });

  it("is valid JavaScript that picks the stored theme, else the OS one", () => {
    const run = (stored: string | null, systemDark: boolean) => {
      const html = { dataset: {} as Record<string, string> };
      new Function("localStorage", "window", "document", THEME_INIT_SCRIPT)(
        { getItem: () => stored },
        { matchMedia: () => ({ matches: systemDark }) },
        { documentElement: html },
      );
      return html.dataset.theme;
    };
    expect(run("dark", false)).toBe("dark");
    expect(run(null, true)).toBe("dark");
    expect(run("garbage", false)).toBe("light");
  });
});
