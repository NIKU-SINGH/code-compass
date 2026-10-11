import type { Point3 } from "./focusSettle";

const EPS = 1e-6;

const len = (p: Point3) => Math.hypot(p.x, p.y, p.z);

/**
 * Control point of the quadratic Bézier that joins two points on a sphere with an arc lifted
 * off the surface, like a flight route on a map.
 *
 * The arc's apex (t = 0.5) sits `lift * chord length` above `radius`, along the outward normal
 * at the midpoint of the two ends, so short edges hug the globe and long ones arch higher.
 *
 * Args:
 *   a: One end of the edge, on the sphere.
 *   b: The other end of the edge, on the sphere.
 *   radius: Sphere radius the ends sit on.
 *   lift: Apex height as a fraction of the chord length.
 *   maxHeight: Ceiling on the apex height, so very long edges stay close to the globe.
 *
 * Returns:
 *   The Bézier control point.
 */
export function arcControlPoint(a: Point3, b: Point3, radius: number, lift = 0.25, maxHeight = Infinity): Point3 {
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
  const midLen = len(mid);
  const chord = Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

  let dir: Point3;
  if (midLen > EPS * Math.max(radius, 1)) {
    dir = { x: mid.x / midLen, y: mid.y / midLen, z: mid.z / midLen };
  } else {
    // Antipodal ends: every direction perpendicular to the chord is equally "outward".
    const d = { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
    const axis = Math.abs(d.x) < Math.abs(d.y) ? { x: 1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 };
    const cross = {
      x: d.y * axis.z - d.z * axis.y,
      y: d.z * axis.x - d.x * axis.z,
      z: d.x * axis.y - d.y * axis.x,
    };
    const l = len(cross) || 1;
    dir = { x: cross.x / l, y: cross.y / l, z: cross.z / l };
  }

  // Apex of a quadratic Bézier = (a + 2c + b) / 4 = (mid + c) / 2, so c = 2 * apex - mid.
  const reach = 2 * (radius + Math.min(chord * lift, maxHeight)) - midLen;
  return { x: dir.x * reach, y: dir.y * reach, z: dir.z * reach };
}

/**
 * Samples a quadratic Bézier into a flat `[x, y, z, ...]` array of `segments + 1` points.
 */
export function sampleArc(
  a: Point3,
  control: Point3,
  b: Point3,
  segments: number,
  out: Float32Array = new Float32Array((segments + 1) * 3)
): Float32Array {
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const u = 1 - t;
    out[i * 3] = u * u * a.x + 2 * u * t * control.x + t * t * b.x;
    out[i * 3 + 1] = u * u * a.y + 2 * u * t * control.y + t * t * b.y;
    out[i * 3 + 2] = u * u * a.z + 2 * u * t * control.z + t * t * b.z;
  }
  return out;
}

/**
 * Opacity for something on the globe as seen from the camera: 1 on the near hemisphere, easing
 * down to `minOpacity` once it has turned past the limb to the far side.
 *
 * Args:
 *   pos: Position of the node or arc apex, relative to the globe's centre.
 *   cam: Camera position, relative to the globe's centre.
 *   minOpacity: Opacity on the far side.
 */
export function depthOpacity(pos: Point3, cam: Point3, minOpacity = 0.22): number {
  const pl = len(pos);
  const cl = len(cam);
  if (pl < EPS || cl < EPS) return 1;
  const facing = (pos.x * cam.x + pos.y * cam.y + pos.z * cam.z) / (pl * cl);
  const t = Math.min(1, Math.max(0, (facing + 0.1) / 0.3));
  const eased = t * t * (3 - 2 * t);
  return minOpacity + (1 - minOpacity) * eased;
}

/**
 * True when a point on the globe is on the hemisphere facing away from the camera, i.e. hidden
 * behind the globe.
 */
export function isFarSide(pos: Point3, cam: Point3): boolean {
  return pos.x * cam.x + pos.y * cam.y + pos.z * cam.z <= 0;
}

/**
 * Evenly spread points on a sphere (Fibonacci lattice) as a flat `[x, y, z, ...]` array.
 */
export function fibonacciSphere(count: number, radius: number): Float32Array {
  const out = new Float32Array(count * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = count === 1 ? 0 : 1 - (i / (count - 1)) * 2;
    const ring = Math.sqrt(1 - y * y);
    const theta = golden * i;
    out[i * 3] = Math.cos(theta) * ring * radius;
    out[i * 3 + 1] = y * radius;
    out[i * 3 + 2] = Math.sin(theta) * ring * radius;
  }
  return out;
}

/** Screen-space rectangle centred on `(x, y)`, in pixels. */
export interface LabelBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Greedy label decluttering: walks `boxes` in priority order (most important first) and keeps a
 * label only if it does not overlap one already kept. Boxes flagged in `forced` are always kept
 * and are expected to come first.
 *
 * Returns:
 *   Whether each box (same index) should be shown.
 */
export function pickNonOverlapping(boxes: ReadonlyArray<LabelBox>, forced: ReadonlyArray<boolean>): boolean[] {
  const kept: LabelBox[] = [];
  return boxes.map((b, i) => {
    const clear = !kept.some(
      (k) => Math.abs(k.x - b.x) < (k.w + b.w) / 2 && Math.abs(k.y - b.y) < (k.h + b.h) / 2
    );
    const show = forced[i] || clear;
    if (show) kept.push(b);
    return show;
  });
}

/**
 * Where to put an arrowhead so it points along an arc into its target node.
 *
 * Args:
 *   prev: Second-to-last sampled point of the arc.
 *   end: Last point of the arc, the centre of the target node.
 *   standoff: Distance from `end` back along the arc to the arrow's tip, so the head stops at
 *     the node's edge instead of sinking into it.
 *   length: Length of the arrowhead.
 *
 * Returns:
 *   The unit direction of travel and the centre of the arrowhead.
 */
export function arrowPlacement(
  prev: Point3,
  end: Point3,
  standoff: number,
  length: number
): { dir: Point3; center: Point3 } {
  const d = { x: end.x - prev.x, y: end.y - prev.y, z: end.z - prev.z };
  const l = len(d) || 1;
  const dir = { x: d.x / l, y: d.y / l, z: d.z / l };
  const back = standoff + length / 2;
  return {
    dir,
    center: { x: end.x - dir.x * back, y: end.y - dir.y * back, z: end.z - dir.z * back },
  };
}
