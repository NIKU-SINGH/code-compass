"use client";

import { useSyncExternalStore } from "react";
import { onColorSchemeChange } from "@/lib/cssColor";

let version = 0;
const subscribe = (notify: () => void) =>
  onColorSchemeChange(() => {
    version += 1;
    notify();
  });

/** Counter that increments whenever the OS colour scheme flips, to re-run colour-dependent effects. */
export function useColorSchemeVersion(): number {
  return useSyncExternalStore(subscribe, () => version, () => 0);
}
