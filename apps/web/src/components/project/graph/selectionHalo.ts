import * as THREE from "three";
import { resolveCssColor } from "@/lib/cssColor";

const SIZE = 128;

function drawHalo(color: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = SIZE;
  const ctx = canvas.getContext("2d")!;
  const c = SIZE / 2;

  // Soft glow fading out to the edge, then a crisp ring at about a third of the way out.
  const glow = ctx.createRadialGradient(c, c, 0, c, c, c);
  glow.addColorStop(0, `${color}99`);
  glow.addColorStop(0.5, `${color}33`);
  glow.addColorStop(1, `${color}00`);
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, SIZE, SIZE);

  ctx.strokeStyle = color;
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.arc(c, c, SIZE * 0.2, 0, Math.PI * 2);
  ctx.stroke();
  return new THREE.CanvasTexture(canvas);
}

let material: THREE.SpriteMaterial | null = null;

function sharedMaterial(): THREE.SpriteMaterial {
  if (!material) {
    material = new THREE.SpriteMaterial({
      map: drawHalo(resolveCssColor("--primary")),
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
  }
  return material;
}

/** Ring-and-glow marker for the selected node; one per node, all sharing one texture. */
export function createHalo(nodeRadius: number): THREE.Sprite {
  const halo = new THREE.Sprite(sharedMaterial());
  halo.scale.setScalar(nodeRadius * 8);
  halo.renderOrder = 10;
  halo.raycast = () => {};
  halo.visible = false;
  return halo;
}

/** Redraws the shared texture after a colour-scheme change. */
export function recolorHalo() {
  if (!material) return;
  material.map?.dispose();
  material.map = drawHalo(resolveCssColor("--primary"));
  material.needsUpdate = true;
}
