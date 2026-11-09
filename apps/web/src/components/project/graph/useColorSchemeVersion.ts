"use client";

import { useSyncExternalStore } from "react";
import { getColorSchemeVersion, onColorSchemeChange } from "@/lib/cssColor";

/** Counter that increments whenever the OS colour scheme flips, to re-run colour-dependent effects. */
export function useColorSchemeVersion(): number {
  return useSyncExternalStore(onColorSchemeChange, getColorSchemeVersion, () => 0);
}
