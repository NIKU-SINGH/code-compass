import * as THREE from "three";
import SpriteText from "three-spritetext";
import { resolveCssColor } from "@/lib/cssColor";
import type { Point3 } from "./focusSettle";
import { arcControlPoint, arrowPlacement, sampleArc } from "./globeMath";

const SEGMENTS = 20;
const LABEL_HEIGHT = 7;
// Arc apex height: a fraction of the chord, capped at a fraction of the globe radius.
const ARC_LIFT = 0.12;
const ARC_MAX_HEIGHT = 0.25;
const ARROW_LENGTH = 10;
const ARROW_RADIUS = 3.2;
// Arrow tip stops this far short of the target's centre, i.e. at the node's edge.
const ARROW_STANDOFF = 7;
const UP = new THREE.Vector3(0, 1, 0);

/** One edge drawn as an arc over the globe, with its type label parked at the apex. */
export interface ArcLink {
  object: THREE.Group;
  line: THREE.Line<THREE.BufferGeometry, THREE.LineBasicMaterial>;
  label: SpriteText;
  /** Arrowhead at the target end, showing which way the edge points. */
  arrow: THREE.Mesh<THREE.ConeGeometry, THREE.MeshBasicMaterial>;
  /** Midpoint of the arc, in world space; used for depth shading. */
  apex: THREE.Vector3;
}

/** Translucent card colour behind label text, so it stays legible over arcs and nodes. */
export function labelBackground(): string {
  return `${resolveCssColor("--card")}e0`;
}

const scratch = new Float32Array((SEGMENTS + 1) * 3);

export function createArcLink(color: string, labelText: string, labelColor: string): ArcLink {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(scratch.length), 3));
  const line = new THREE.Line(
    geometry,
    new THREE.LineBasicMaterial({ color, transparent: true, depthWrite: false })
  );
  line.frustumCulled = false;
  // Arcs are not pick targets; their stale bounding sphere would only swallow clicks meant for nodes.
  line.raycast = () => {};

  const label = new SpriteText(labelText, LABEL_HEIGHT, labelColor);
  label.fontFace = "ui-monospace, monospace";
  label.fontWeight = "600";
  label.material.depthWrite = false;
  label.padding = 1.2;
  label.borderRadius = 1.5;
  label.backgroundColor = labelBackground();
  label.raycast = () => {};
  label.visible = false;

  const arrow = new THREE.Mesh(
    new THREE.ConeGeometry(ARROW_RADIUS, ARROW_LENGTH, 10),
    new THREE.MeshBasicMaterial({ color, transparent: true, depthWrite: false })
  );
  arrow.raycast = () => {};
  arrow.visible = false;

  const object = new THREE.Group();
  object.add(line, label, arrow);
  object.userData.arcLink = true;
  return { object, line, label, arrow, apex: new THREE.Vector3() };
}

/** Re-fits the arc to its (moving) end nodes. */
export function updateArcLink(arc: ArcLink, start: Point3, end: Point3, radius: number) {
  const control = arcControlPoint(start, end, radius, ARC_LIFT, radius * ARC_MAX_HEIGHT);
  sampleArc(start, control, end, SEGMENTS, scratch);
  const position = arc.line.geometry.getAttribute("position") as THREE.BufferAttribute;
  (position.array as Float32Array).set(scratch);
  position.needsUpdate = true;

  const mid = SEGMENTS / 2;
  arc.apex.set(scratch[mid * 3], scratch[mid * 3 + 1], scratch[mid * 3 + 2]);
  arc.label.position.copy(arc.apex);

  const prev = { x: scratch[(SEGMENTS - 1) * 3], y: scratch[(SEGMENTS - 1) * 3 + 1], z: scratch[(SEGMENTS - 1) * 3 + 2] };
  const { dir, center } = arrowPlacement(prev, end, ARROW_STANDOFF, ARROW_LENGTH);
  arc.arrow.position.set(center.x, center.y, center.z);
  arc.arrow.quaternion.setFromUnitVectors(UP, new THREE.Vector3(dir.x, dir.y, dir.z));
}

export function disposeArcLink(arc: ArcLink) {
  arc.line.geometry.dispose();
  arc.line.material.dispose();
  arc.arrow.geometry.dispose();
  arc.arrow.material.dispose();
  arc.label.material.map?.dispose();
  arc.label.material.dispose();
}
