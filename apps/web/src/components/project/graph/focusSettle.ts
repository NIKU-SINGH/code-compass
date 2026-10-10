export interface Point3 {
  x: number;
  y: number;
  z: number;
}

/** True when a node moved less than `eps` units between two consecutive layout samples. */
export function isPositionStable(prev: Point3 | null, next: Point3, eps: number): boolean {
  if (!prev) return false;
  return Math.hypot(next.x - prev.x, next.y - prev.y, next.z - prev.z) < eps;
}
