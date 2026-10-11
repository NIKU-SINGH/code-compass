import * as THREE from "three";
import { resolveCssColor } from "@/lib/cssColor";
import { fibonacciSphere } from "./globeMath";

const SURFACE_INSET = 0.97;
const DOT_COUNT = 1800;

const BODY_VERTEX = `
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;
// One sphere: lit slightly toward the viewer, with a soft accent tint building up at the limb.
const BODY_FRAGMENT = `
  uniform vec3 baseColor;
  uniform vec3 rimColor;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    float facing = abs(dot(normalize(vNormal), normalize(vView)));
    float rim = pow(1.0 - facing, 3.0);
    vec3 lit = baseColor * (0.8 + 0.2 * facing);
    gl_FragColor = vec4(mix(lit, rimColor, rim * 0.3), 0.92);
  }
`;

/**
 * The globe body: a single softly shaded sphere just inside the node surface, with an accent
 * tint at its edge, and a lattice of small dots that gives the far side some texture.
 *
 * Colours come from the theme tokens (`--card`, `--primary`, `--foreground`), so call `recolor`
 * when the colour scheme changes.
 */
export class GlobeShell {
  readonly group = new THREE.Group();
  private readonly body: THREE.Mesh<THREE.SphereGeometry, THREE.ShaderMaterial>;
  private readonly dots: THREE.Points<THREE.BufferGeometry, THREE.PointsMaterial>;

  constructor(radius: number) {
    const surface = radius * SURFACE_INSET;

    this.body = new THREE.Mesh(
      new THREE.SphereGeometry(surface, 64, 48),
      new THREE.ShaderMaterial({
        uniforms: { baseColor: { value: new THREE.Color() }, rimColor: { value: new THREE.Color() } },
        vertexShader: BODY_VERTEX,
        fragmentShader: BODY_FRAGMENT,
        transparent: true,
        depthWrite: false,
      })
    );
    // Not a pick target: clicks must reach the nodes, not the globe.
    this.body.raycast = () => {};

    const dotGeometry = new THREE.BufferGeometry();
    dotGeometry.setAttribute("position", new THREE.BufferAttribute(fibonacciSphere(DOT_COUNT, surface), 3));
    this.dots = new THREE.Points(
      dotGeometry,
      new THREE.PointsMaterial({ size: 1.1, transparent: true, opacity: 0.35, depthWrite: false })
    );
    this.dots.raycast = () => {};

    // Drawn before nodes and arcs so they always sit on top of the body.
    for (const part of [this.body, this.dots]) {
      part.renderOrder = -1;
      this.group.add(part);
    }
    this.recolor();
  }

  /** Re-reads the theme tokens. */
  recolor() {
    this.body.material.uniforms.baseColor.value.set(resolveCssColor("--card"));
    this.body.material.uniforms.rimColor.value.set(resolveCssColor("--primary"));
    this.dots.material.color.set(resolveCssColor("--foreground"));
  }

  dispose() {
    this.group.removeFromParent();
    for (const part of [this.body, this.dots]) {
      part.geometry.dispose();
      part.material.dispose();
    }
  }
}
