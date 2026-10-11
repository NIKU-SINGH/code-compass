import * as THREE from "three";
import SpriteText from "three-spritetext";
import { NODE_SIZE, colorForEdge, colorForNode } from "./graphStyle";
import { colorForFolder, folderOf } from "./groupColor";
import { createHalo, recolorHalo } from "./selectionHalo";
import { createArcLink, labelBackground, updateArcLink, type ArcLink } from "./arcLinks";
import { depthOpacity, pickNonOverlapping, type LabelBox } from "./globeMath";
import { linkTouches } from "./focusNeighbourhood";
import type { EdgeType } from "./useGraphData";
import type { VisibleNode, VisibleEdge } from "./useExpandableGraph";

const NODE_RADIUS_SCALE = 2;
// Arc opacity at rest, when touching the lit node, and when off to the side of it.
const LINK_OPACITY = 0.55;
const LINK_LIT_OPACITY = 1;
const LINK_DIM_OPACITY = 0.05;
// Without a selection only this many names are drawn, front-most first, so the globe stays readable.
const MAX_IDLE_LABELS = 28;
const SELECTED_SCALE = 1.35;
// Labels on nodes turned past this depth opacity (towards the far side) are hidden outright.
const LABEL_MIN_DEPTH = 0.6;
const LABEL_CHAR_PX = 5;
const LABEL_HEIGHT_PX = 10;
const UNFOCUSED_OPACITY = 0.15;
const NODE_LABEL_HEIGHT = 8;
// Invisible, larger-than-the-dot sphere that makes small nodes easy to click.
const HIT_RADIUS_SCALE = 2.4;

type Positioned<T> = T & { x?: number; y?: number; z?: number };
type LinkObj = Omit<VisibleEdge, "source" | "target"> & {
  source: Positioned<VisibleNode> | string;
  target: Positioned<VisibleNode> | string;
};

const tintedLinks = new WeakSet<object>();

/** Files take their folder's colour so related files read as a group; other kinds keep their kind colour. */
function nodeColor(node: VisibleNode): string {
  return node.type === "File" ? colorForFolder(folderOf(node.publicId)) : colorForNode(node.type);
}

/** Import arcs take the colour of the file doing the importing; other edge types keep their own. */
function linkColor(link: LinkObj): string | null {
  if (link.type !== "IMPORTS" || typeof link.source === "string") return null;
  return nodeColor(link.source);
}

/** HTML for the hover tooltip: name, kind and where it lives. Repo text is escaped. */
export function nodeTooltip(n: object): string {
  const node = n as VisibleNode;
  const esc = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
  const path = node.publicId.startsWith("file::")
    ? node.publicId.slice("file::".length)
    : node.publicId.split("::")[0];
  return `<b>${esc(node.label)}</b><br/>${esc(node.type)} · ${esc(path)}`;
}

/** Name shown on the globe: files get their parent folder too, since many are just `__init__.py`. */
export function labelTextFor(node: Pick<VisibleNode, "type" | "label" | "publicId">): string {
  if (node.type !== "File") return node.label;
  const path = node.publicId.startsWith("file::") ? node.publicId.slice("file::".length) : node.label;
  return path.split("/").slice(-2).join("/");
}

interface NodeParts {
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  label: SpriteText;
  halo: THREE.Sprite;
}

/** What the per-frame pass needs to know about the current view. */
export interface ShadingView {
  camera: THREE.Vector3;
  showLabels: boolean;
  focusId: string | null;
  /** The focused node plus its neighbours; null when nothing is focused. */
  focusSet: Set<string> | null;
}

/** Minimal slice of the 3d-force-graph instance this module drives. */
export interface ShadedGraph {
  graphData(): { nodes: object[]; links: object[] };
  graph2ScreenCoords(x: number, y: number, z: number): { x: number; y: number };
}

const nodeParts = new WeakMap<object, NodeParts>();
const linkParts = new WeakMap<object, ArcLink>();

/** `nodeThreeObject` accessor: a small sphere with a name label above it. */
export function createNodeObject(n: object): THREE.Object3D {
  const node = n as VisibleNode;
  const radius = Math.cbrt(NODE_SIZE[node.type] ?? 4) * NODE_RADIUS_SCALE;
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 16, 12),
    new THREE.MeshBasicMaterial({ color: nodeColor(node), transparent: true })
  );
  const hit = new THREE.Mesh(
    new THREE.SphereGeometry(radius * HIT_RADIUS_SCALE, 8, 6),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
  );
  const label = new SpriteText(labelTextFor(node), NODE_LABEL_HEIGHT, nodeColor(node));
  label.fontFace = "ui-monospace, monospace";
  label.material.depthWrite = false;
  label.padding = 1.2;
  label.borderRadius = 1.5;
  label.backgroundColor = labelBackground();
  label.position.set(0, radius + NODE_LABEL_HEIGHT + 1, 0);
  label.visible = false;

  const halo = createHalo(radius);

  const group = new THREE.Group();
  group.add(halo, mesh, hit, label);
  nodeParts.set(n, { mesh, label, halo });
  return group;
}

/** `linkThreeObject` accessor: an arc over the globe plus its type label. */
export function createLinkObject(l: object): THREE.Object3D {
  const link = l as LinkObj;
  const arc = createArcLink(
    colorForEdge(link.type as EdgeType),
    link.type,
    colorForEdge(link.type as EdgeType)
  );
  linkParts.set(l, arc);
  return arc.object;
}

/** `linkPositionUpdate` handler: re-fits the arc to its end nodes. Returns true = handled. */
export function positionLinkObject(
  _obj: THREE.Object3D,
  ends: { start: { x: number; y: number; z: number }; end: { x: number; y: number; z: number } },
  l: object,
  radius: number
): boolean {
  const arc = linkParts.get(l);
  if (arc) updateArcLink(arc, ends.start, ends.end, radius);
  return true;
}

/**
 * Per-frame pass: fades nodes, arcs and labels by how far round the back of the globe they
 * are, dims everything outside the focused node's neighbourhood, and decides which labels show.
 */
export function applyShading(graph: ShadedGraph, view: ShadingView) {
  const { camera, showLabels, focusId, focusSet } = view;
  const data = graph.graphData();

  // Label candidates, then thinned so overlapping names don't pile up on screen. The focused
  // neighbourhood is forced on and ranked first; otherwise bigger kinds (files) win.
  const candidates: { parts: NodeParts; box: LabelBox; forced: boolean; rank: number }[] = [];
  for (const n of data.nodes as Positioned<VisibleNode>[]) {
    const parts = nodeParts.get(n);
    if (!parts) continue;
    const depth = depthOpacity({ x: n.x ?? 0, y: n.y ?? 0, z: n.z ?? 0 }, camera);
    const dim = focusSet && !focusSet.has(n.id) ? UNFOCUSED_OPACITY : 1;
    parts.mesh.material.opacity = depth * dim;
    parts.mesh.scale.setScalar(n.id === focusId ? SELECTED_SCALE : 1);
    parts.halo.visible = n.id === focusId;
    parts.label.material.opacity = depth * dim;
    parts.label.visible = false;

    const forced = focusSet?.has(n.id) === true;
    if (!(forced || (showLabels && !focusSet)) || depth < LABEL_MIN_DEPTH) continue;
    const s = graph.graph2ScreenCoords(n.x ?? 0, n.y ?? 0, n.z ?? 0);
    candidates.push({
      parts,
      forced,
      rank: (forced ? 1000 : 0) + (NODE_SIZE[n.type] ?? 0) * 10 + depth,
      box: { x: s.x, y: s.y, w: parts.label.text.length * LABEL_CHAR_PX, h: LABEL_HEIGHT_PX },
    });
  }
  candidates.sort((a, b) => b.rank - a.rank);
  if (!focusSet) candidates.length = Math.min(candidates.length, MAX_IDLE_LABELS);
  const shown = pickNonOverlapping(
    candidates.map((c) => c.box),
    candidates.map((c) => c.forced)
  );
  candidates.forEach((c, i) => (c.parts.label.visible = shown[i]));

  for (const l of data.links as LinkObj[]) {
    const arc = linkParts.get(l);
    if (!arc) continue;
    if (!tintedLinks.has(l)) {
      const tint = linkColor(l);
      if (tint) {
        arc.line.material.color.set(tint);
        arc.arrow.material.color.set(tint);
        arc.label.color = tint;
        tintedLinks.add(l);
      }
    }
    const touches = focusId !== null && linkTouches(focusId, l);
    const depth = depthOpacity(arc.apex, camera);
    const base =
      focusId === null ? LINK_OPACITY : touches ? LINK_LIT_OPACITY : LINK_DIM_OPACITY;
    arc.line.material.opacity = base * depth;
    arc.arrow.material.opacity = base * depth;
    arc.arrow.visible = touches;
    arc.label.material.opacity = depth;
    arc.label.visible = showLabels && touches;
  }
}

/** Re-reads theme colours after a colour-scheme change. */
export function recolorShading(graph: ShadedGraph) {
  recolorHalo();
  for (const n of graph.graphData().nodes as VisibleNode[]) {
    const parts = nodeParts.get(n);
    if (!parts) continue;
    const color = nodeColor(n);
    parts.mesh.material.color.set(color);
    parts.label.color = color;
    parts.label.backgroundColor = labelBackground();
  }
  for (const l of graph.graphData().links as LinkObj[]) {
    const arc = linkParts.get(l);
    if (!arc) continue;
    const color = linkColor(l) ?? colorForEdge(l.type as EdgeType);
    arc.line.material.color.set(color);
    arc.arrow.material.color.set(color);
    arc.label.color = color;
    arc.label.backgroundColor = labelBackground();
  }
}
