"use client";

import { useEffect, useImperativeHandle, useRef, forwardRef } from "react";
import ForceGraph3D, { ForceGraph3DInstance } from "3d-force-graph";
import type { VisibleNode, VisibleEdge } from "./useExpandableGraph";
import { NODE_SIZE, EDGE_COLOR, colorForNode } from "./graphStyle";
import type { EdgeType } from "./useGraphData";
import { mergeGraphData } from "./mergeGraphData";

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
// with node count (area ∝ r², so r ∝ √n).
function radiusForNodeCount(count: number) {
  return Math.max(120, Math.sqrt(Math.max(count, 1)) * 22);
}

interface Props {
  nodes: VisibleNode[];
  edges: VisibleEdge[];
  showLabels: boolean;
  onNodeClick: (node: VisibleNode, screenX: number, screenY: number) => void;
  onNodeDblClick: (node: VisibleNode) => void;
  onBackgroundClick: () => void;
}

export const GraphCanvas3D = forwardRef<GraphCanvasHandle, Props>(function GraphCanvas3D(
  { nodes, edges, showLabels, onNodeClick, onNodeDblClick, onBackgroundClick },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraph3DInstance | null>(null);
  const nodeCacheRef = useRef(new Map<string, VisibleNode>());
  const radiusRef = useRef(radiusForNodeCount(0));
  const hasFramedRef = useRef(false);

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
      .nodeColor((n) => colorForNode((n as VisibleNode).filePath, (n as VisibleNode).type))
      .nodeVal((n) => NODE_SIZE[(n as VisibleNode).type] ?? 4)
      .nodeLabel((n) => (n as VisibleNode).label)
      .linkColor((l) => EDGE_COLOR[((l as unknown as VisibleEdge).type as EdgeType)] ?? "rgba(255,255,255,0.2)")
      .linkOpacity(0.6)
      .linkDirectionalParticles(1)
      .linkDirectionalParticleWidth(1.5)
      .linkDirectionalParticleSpeed(0.004)
      .showNavInfo(false)
      .onBackgroundClick(() => onBackgroundClick());

    graph.d3Force("charge")?.strength(-40);
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

    return () => {
      graph._destructor?.();
      graphRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    radiusRef.current = radiusForNodeCount(nodes.length);
    graph.graphData(mergeGraphData(nodeCacheRef.current, nodes, edges));

    if (!hasFramedRef.current && nodes.length > 0) {
      hasFramedRef.current = true;
      graph.cameraPosition({ z: radiusRef.current * 3 }, undefined, 0);
    }
  }, [nodes, edges]);

  useEffect(() => {
    graphRef.current?.nodeLabel((n) => (showLabels ? (n as VisibleNode).label : ""));
  }, [showLabels]);

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
