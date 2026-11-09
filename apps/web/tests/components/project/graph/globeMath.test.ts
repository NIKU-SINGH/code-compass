import { describe, expect, it } from "vitest";
import {
  arcControlPoint,
  depthOpacity,
  arrowPlacement,
  fibonacciSphere,
  isFarSide,
  pickNonOverlapping,
  sampleArc,
} from "@/components/project/graph/globeMath";

const R = 100;
const norm = (p: { x: number; y: number; z: number }) => Math.hypot(p.x, p.y, p.z);

describe("arcControlPoint", () => {
  it("puts the arc apex above the sphere, along the outward normal", () => {
    const a = { x: R, y: 0, z: 0 };
    const b = { x: 0, y: R, z: 0 };
    const c = arcControlPoint(a, b, R, 0.25);
    const mid = sampleArc(a, c, b, 2); // 3 points: start, apex (t = 0.5), end
    const apexLen = Math.hypot(mid[3], mid[4], mid[5]);
    const chord = Math.hypot(R, R);
    expect(apexLen).toBeCloseTo(R + chord * 0.25, 4);
    expect(c.x).toBeCloseTo(c.y, 6);
    expect(c.z).toBeCloseTo(0, 6);
  });

  it("lifts longer edges higher than short ones", () => {
    const o = { x: R, y: 0, z: 0 };
    const near = arcControlPoint(o, { x: R * 0.99, y: R * 0.14, z: 0 }, R);
    const far = arcControlPoint(o, { x: 0, y: R, z: 0 }, R);
    expect(norm(far)).toBeGreaterThan(norm(near));
  });

  it("caps the apex height for very long edges", () => {
    const c = arcControlPoint({ x: R, y: 0, z: 0 }, { x: -R * 0.9, y: R * 0.4, z: 0 }, R, 0.25, 10);
    const apex = sampleArc({ x: R, y: 0, z: 0 }, c, { x: -R * 0.9, y: R * 0.4, z: 0 }, 2);
    // Apex = mid-point of the chord pushed out by at most 10 beyond the sphere radius.
    expect(Math.hypot(apex[3], apex[4], apex[5])).toBeCloseTo(R + 10, 4);
  });

  it("handles antipodal ends without producing NaN", () => {
    const c = arcControlPoint({ x: R, y: 0, z: 0 }, { x: -R, y: 0, z: 0 }, R);
    expect(Number.isFinite(c.x + c.y + c.z)).toBe(true);
    expect(norm(c)).toBeGreaterThan(R);
  });
});

describe("sampleArc", () => {
  it("starts and ends exactly on the endpoints", () => {
    const a = { x: 1, y: 2, z: 3 };
    const b = { x: 4, y: 5, z: 6 };
    const pts = sampleArc(a, { x: 0, y: 0, z: 0 }, b, 8);
    expect(pts.length).toBe(27);
    expect([pts[0], pts[1], pts[2]]).toEqual([1, 2, 3]);
    expect([pts[24], pts[25], pts[26]]).toEqual([4, 5, 6]);
  });
});

describe("depthOpacity", () => {
  const cam = { x: 0, y: 0, z: 500 };

  it("is fully opaque facing the camera and dimmed on the far side", () => {
    expect(depthOpacity({ x: 0, y: 0, z: R }, cam)).toBeCloseTo(1, 6);
    expect(depthOpacity({ x: 0, y: 0, z: -R }, cam)).toBeCloseTo(0.22, 6);
  });

  it("falls monotonically as a point turns away", () => {
    const at = (deg: number) => {
      const r = (deg * Math.PI) / 180;
      return depthOpacity({ x: Math.sin(r) * R, y: 0, z: Math.cos(r) * R }, cam);
    };
    const samples = [0, 60, 90, 110, 180].map(at);
    for (let i = 1; i < samples.length; i++) {
      expect(samples[i]).toBeLessThanOrEqual(samples[i - 1]);
    }
  });

  it("treats a degenerate position as visible", () => {
    expect(depthOpacity({ x: 0, y: 0, z: 0 }, cam)).toBe(1);
  });
});

describe("isFarSide", () => {
  const cam = { x: 0, y: 0, z: 500 };
  it("is true only for points on the hemisphere facing away", () => {
    expect(isFarSide({ x: 0, y: 0, z: -R }, cam)).toBe(true);
    expect(isFarSide({ x: 10, y: 0, z: -1 }, cam)).toBe(true);
    expect(isFarSide({ x: 0, y: 0, z: R }, cam)).toBe(false);
  });
});

describe("fibonacciSphere", () => {
  it("returns the requested number of points, all on the sphere", () => {
    const pts = fibonacciSphere(50, R);
    expect(pts.length).toBe(150);
    for (let i = 0; i < 50; i++) {
      expect(Math.hypot(pts[i * 3], pts[i * 3 + 1], pts[i * 3 + 2])).toBeCloseTo(R, 3);
    }
  });
});

describe("pickNonOverlapping", () => {
  const box = (x: number, y: number) => ({ x, y, w: 40, h: 14 });

  it("drops a lower-priority label that overlaps a kept one", () => {
    expect(pickNonOverlapping([box(0, 0), box(10, 5), box(100, 0)], [false, false, false])).toEqual([
      true,
      false,
      true,
    ]);
  });

  it("always keeps forced labels, even when they overlap", () => {
    expect(pickNonOverlapping([box(0, 0), box(10, 5)], [true, true])).toEqual([true, true]);
  });
});

describe("arrowPlacement", () => {
  it("points along the arc and stops short of the target", () => {
    const { dir, center } = arrowPlacement({ x: 0, y: 0, z: 0 }, { x: 10, y: 0, z: 0 }, 6, 4);
    expect(dir).toEqual({ x: 1, y: 0, z: 0 });
    // Tip at standoff (6) before the end; the head's centre is half its length further back.
    expect(center.x).toBeCloseTo(10 - 6 - 2, 6);
  });

  it("copes with a zero-length segment", () => {
    const { dir } = arrowPlacement({ x: 1, y: 1, z: 1 }, { x: 1, y: 1, z: 1 }, 6, 4);
    expect(Number.isFinite(dir.x + dir.y + dir.z)).toBe(true);
  });
});
