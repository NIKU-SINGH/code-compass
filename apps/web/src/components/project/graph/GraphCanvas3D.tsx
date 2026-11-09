"use client";

import { useEffect, useImperativeHandle, useRef, forwardRef } from "react";
import ForceGraph3D, { ForceGraph3DInstance } from "3d-force-graph";
import type { VisibleNode, VisibleEdge } from "./useExpandableGraph";
import { isPositionStable, type Point3 } from "./focusSettle";
import { useColorSchemeVersion } from "./useColorSchemeVersion";
import { mergeGraphData } from "./mergeGraphData";
import { GlobeShell } from "./GlobeShell";
import { neighbourhoodOf } from "./focusNeighbourhood";
import { isFarSide } from "./globeMath";
import {
  applyShading,
  createLinkObject,
  createNodeObject,
  nodeTooltip,
  positionLinkObject,
  recolorShading,
  type ShadingView,
} from "./globeShading";

export interface GraphCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
}

interface SphereForceNode {
  x?: number;
  y?: number;
  z?: number;
}

// Projects every node's position onto the surface of a sphere after each
// physics tick, so the graph reads as a globe instead of a free-floating
// force-directed cloud. Running as a hard clamp (rather than a velocity
// nudge inside the d3 force pass) keeps every node locked to the radius
// regardless of how strong the charge/link forces pulling it around are —
// only the angular position drifts, which is what spreads nodes across the
// sphere's surface.
function clampToSphere(nodes: SphereForceNode[], radius: number) {
  for (const n of nodes) {
    const x = n.x ?? (Math.random() - 0.5);
    const y = n.y ?? (Math.random() - 0.5);
    const z = n.z ?? (Math.random() - 0.5);
    const len = Math.sqrt(x * x + y * y + z * z) || 1;
    n.x = (x / len) * radius;
    n.y = (y / len) * radius;
    n.z = (z / len) * radius;
  }
}

// Roughly keeps point density constant as the sphere's surface area grows
// with node count (area ∝ r², so r ∝ √n). Fed the whole index's node count,
// not the visible one, so filtering never resizes the globe.
function radiusForNodeCount(count: number) {
  return Math.max(120, Math.sqrt(Math.max(count, 1)) * 30);
}

const FOCUS_DISTANCE = 140;
const FOCUS_TWEEN_MS = 1000;
const REAIM_MS = 300;
const POLL_MS = 120;
const MAX_POLLS = 25;
const STABLE_EPS = 1;

// Moves the camera along the node's radius so it sits in front of the node, looking at it.
// Auto-rotate is stopped, otherwise it would immediately drag the view away again.
function centreOnNode(graph: ForceGraph3DInstance, pos: Point3, durationMs = FOCUS_TWEEN_MS) {
  const ratio = 1 + FOCUS_DISTANCE / (Math.hypot(pos.x, pos.y, pos.z) || 1);
  (graph.controls() as { autoRotate?: boolean }).autoRotate = false;
  graph.cameraPosition({ x: pos.x * ratio, y: pos.y * ratio, z: pos.z * ratio }, pos, durationMs);
}

interface Props {
  nodes: VisibleNode[];
  edges: VisibleEdge[];
  /** Every node in the index, shown or not; sizes the globe so filters leave it fixed. */
  totalNodeCount: number;
  showLabels: boolean;
  onNodeClick: (node: VisibleNode, screenX: number, screenY: number) => void;
  onNodeDblClick: (node: VisibleNode) => void;
  onBackgroundClick: () => void;
  /** Stored id of a node to centre the camera on; re-runs whenever it changes. */
  focusId?: string | null;
  /** Stored id of the clicked node; it and its neighbours stay lit while everything else dims. */
  selectedId?: string | null;
}

export const GraphCanvas3D = forwardRef<GraphCanvasHandle, Props>(function GraphCanvas3D(
  { nodes, edges, totalNodeCount, showLabels, onNodeClick, onNodeDblClick, onBackgroundClick, focusId, selectedId },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraph3DInstance | null>(null);
  const nodeCacheRef = useRef(new Map<string, VisibleNode>());
  const radiusRef = useRef(radiusForNodeCount(0));
  const hasFramedRef = useRef(false);
  const shellRef = useRef<GlobeShell | null>(null);
  // The shading loop runs outside React, so it reads the latest view state from here.
  const viewRef = useRef<Pick<ShadingView, "showLabels" | "focusId" | "focusSet">>({
    showLabels,
    focusId: focusId ?? null,
    focusSet: null,
  });
  const schemeVersion = useColorSchemeVersion();

  useImperativeHandle(ref, () => ({
    zoomIn: () => {
      const cam = graphRef.current?.camera();
      if (cam) graphRef.current!.cameraPosition({ z: cam.position.z * 0.7 }, undefined, 300);
    },
    zoomOut: () => {
      const cam = graphRef.current?.camera();
      if (cam) graphRef.current!.cameraPosition({ z: cam.position.z * 1.4 }, undefined, 300);
    },
  }));

  useEffect(() => {
    if (!containerRef.current) return;
    const graph = new ForceGraph3D(containerRef.current)
      .backgroundColor("rgba(0,0,0,0)")
      .nodeId("id")
      .nodeThreeObject(createNodeObject)
      .nodeThreeObjectExtend(false)
      // The click popover already describes the selected node; don't stack a hover tooltip on it.
      .nodeLabel((n) => {
        const node = n as VisibleNode & { x?: number; y?: number; z?: number };
        const hidden = isFarSide({ x: node.x ?? 0, y: node.y ?? 0, z: node.z ?? 0 }, graph.camera().position);
        return node.id === viewRef.current.focusId || hidden ? "" : nodeTooltip(n);
      })
      .linkThreeObject(createLinkObject)
      .linkThreeObjectExtend(false)
      .linkPositionUpdate((obj, ends, l) =>
        positionLinkObject(obj, ends, l, radiusRef.current)
      )
      .showNavInfo(false)
      .onBackgroundClick(() => onBackgroundClick());

    // Strong repulsion with weak links: connected nodes stay loosely near each other, but the
    // set spreads over the whole globe instead of collapsing into one clump.
    graph.d3Force("charge")?.strength(-250);
    (graph.d3Force("link") as { strength?: (s: number) => void } | undefined)?.strength?.(0.05);
    graph.onEngineTick(() => {
      clampToSphere(graph.graphData().nodes as SphereForceNode[], radiusRef.current);
    });

    const controls = graph.controls() as { autoRotate?: boolean; autoRotateSpeed?: number };
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.4;

    let lastClick = 0;
    let lastNode: string | null = null;
    graph.onNodeClick((n) => {
      const node = n as VisibleNode;
      // Nodes behind the globe are still ray-pickable; a click that lands on one is really a
      // click on empty globe, and must deselect rather than select something unseen.
      const at = node as unknown as { x?: number; y?: number; z?: number };
      if (isFarSide({ x: at.x ?? 0, y: at.y ?? 0, z: at.z ?? 0 }, graph.camera().position)) {
        onBackgroundClick();
        return;
      }
      const now = Date.now();
      if (lastNode === node.id && now - lastClick < 300) {
        onNodeDblClick(node);
      } else {
        const pos = node as unknown as { x?: number; y?: number; z?: number };
        const coords = graph.graph2ScreenCoords(pos.x ?? 0, pos.y ?? 0, pos.z ?? 0);
        const rect = containerRef.current?.getBoundingClientRect();
        onNodeClick(node, (rect?.left ?? 0) + coords.x, (rect?.top ?? 0) + coords.y);
      }
      lastClick = now;
      lastNode = node.id;
    });

    graphRef.current = graph;

    // Drives the depth fade and focus dimming every frame: the physics engine stops ticking
    // once it cools, but the globe keeps turning.
    let frame = requestAnimationFrame(function shade() {
      applyShading(graph, { camera: graph.camera().position, ...viewRef.current });
      frame = requestAnimationFrame(shade);
    });

    return () => {
      cancelAnimationFrame(frame);
      shellRef.current?.dispose();
      shellRef.current = null;
      graph._destructor?.();
      graphRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const radius = radiusForNodeCount(totalNodeCount);
    if (radius !== radiusRef.current || !shellRef.current) {
      radiusRef.current = radius;
      shellRef.current?.dispose();
      shellRef.current = new GlobeShell(radius);
      graph.scene().add(shellRef.current.group);
    }
    graph.graphData(mergeGraphData(nodeCacheRef.current, nodes, edges));

    if (!hasFramedRef.current && nodes.length > 0) {
      hasFramedRef.current = true;
      graph.cameraPosition({ z: radiusRef.current * 4.4 }, undefined, 0);
    }
  }, [nodes, edges, totalNodeCount]);

  // Token colours are cached per scheme, so the globe and every node/arc re-read them.
  useEffect(() => {
    shellRef.current?.recolor();
    if (graphRef.current) recolorShading(graphRef.current);
  }, [schemeVersion]);

  useEffect(() => {
    const lit = selectedId ?? focusId ?? null;
    viewRef.current = {
      showLabels,
      focusId: lit,
      focusSet: lit ? neighbourhoodOf(lit, edges) : null,
    };
  }, [showLabels, selectedId, focusId, edges]);

  // Centres on `focusId` once the force layout has settled around it: the node is usually
  // revealed just before this runs, so early coordinates are still sliding. Sample every
  // POLL_MS until two consecutive samples agree, then tween; give up waiting at the cap and
  // use the last known position. The camera is re-aimed after the tween in case it drifted.
  // Centring switches auto-rotate off (it would drag the view away); it is restored when the
  // focus is cleared, otherwise it stays off.
  useEffect(() => {
    const controls = graphRef.current?.controls() as { autoRotate?: boolean } | undefined;
    if (!focusId) {
      if (controls) controls.autoRotate = true;
      return;
    }
    let attempts = 0;
    let prev: Point3 | null = null;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const position = (): Point3 | null => {
      const n = nodeCacheRef.current.get(focusId) as unknown as Partial<Point3> | undefined;
      return n && n.x !== undefined ? { x: n.x, y: n.y ?? 0, z: n.z ?? 0 } : null;
    };
    const centre = (pos: Point3) => {
      const graph = graphRef.current;
      if (!graph) return;
      centreOnNode(graph, pos);
      timers.push(
        setTimeout(() => {
          const latest = position();
          if (latest && graphRef.current) centreOnNode(graphRef.current, latest, REAIM_MS);
        }, FOCUS_TWEEN_MS + 50)
      );
    };
    const poll = () => {
      const pos = position();
      attempts += 1;
      if (pos && isPositionStable(prev, pos, STABLE_EPS)) return centre(pos);
      if (attempts >= MAX_POLLS) return pos ? centre(pos) : undefined;
      if (pos) prev = pos;
      timers.push(setTimeout(poll, POLL_MS));
    };
    poll();
    return () => timers.forEach(clearTimeout);
  }, [focusId]);

  useEffect(() => {
    function handleResize() {
      if (!containerRef.current || !graphRef.current) return;
      const { width, height } = containerRef.current.getBoundingClientRect();
      graphRef.current.width(width).height(height);
    }
    handleResize();
    const observer = new ResizeObserver(handleResize);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return <div ref={containerRef} className="absolute inset-0" />;
});
