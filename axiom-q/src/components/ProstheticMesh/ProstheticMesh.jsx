import { useEffect, useRef } from "react";
import * as THREE from "three";
import useQuantumStore from "../../store/useQuantumStore";

/* ── Color ramp: green (rest) → cyan → yellow → orange → red (heavy drift) ─── */
function kpaToColor(kpa) {
  // Stop points tuned to backend heatmap ranges (8..30 kPa).
  const stops = [
    { k: 8.0,  c: [0.00, 1.00, 0.25] },  // NEON_GREEN
    { k: 11.0, c: [0.30, 0.95, 0.95] },  // cyan/teal
    { k: 14.0, c: [0.95, 0.85, 0.20] },  // yellow
    { k: 18.0, c: [0.95, 0.55, 0.10] },  // orange
    { k: 24.0, c: [1.00, 0.18, 0.18] },  // red
    { k: 30.0, c: [0.85, 0.05, 0.65] },  // magenta (peak / compartment)
  ];
  const x = Math.max(8.0, Math.min(30.0, kpa));
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    if (x >= a.k && x <= b.k) {
      const t = (x - a.k) / (b.k - a.k);
      return [
        a.c[0] + (b.c[0] - a.c[0]) * t,
        a.c[1] + (b.c[1] - a.c[1]) * t,
        a.c[2] + (b.c[2] - a.c[2]) * t,
      ];
    }
  }
  return stops[stops.length - 1].c;
}

const ZONE_LABELS = ["proximal", "mid", "distal"];
const ZONE_TINTS = [0xa855f7, 0x00f0ff, 0x39ff14];

/**
 * 36-cell Three.js prosthetic mesh.
 *
 * Each cell is an InstancedMesh entry colored by the latest
 * ``cells[].kpa`` value from /ws/prosthetic.
 *
 * 3-zone highlighting is rendered as a tinted plate beneath each
 * ``(row+col) % 3`` band (proximal / mid / distal), wired into the
 * mesh group the VLM corrections flow into.
 */
export default function ProstheticMesh() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      35,
      canvas.clientWidth / Math.max(canvas.clientHeight, 1),
      0.1,
      100
    );
    camera.position.set(0, 5.4, 5.6);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Limb-socket backdrop (dome under the cell grid)
    const baseGeo = new THREE.CylinderGeometry(3.2, 3.2, 0.4, 64);
    const baseMat = new THREE.MeshBasicMaterial({
      color: 0x0a0e14,
      transparent: true,
      opacity: 0.85,
    });
    const base = new THREE.Mesh(baseGeo, baseMat);
    base.position.y = -0.32;
    scene.add(base);

    // Ring outline for visual anchoring
    const ringGeo = new THREE.RingGeometry(3.0, 3.25, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.30,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -0.13;
    scene.add(ring);

    // 3-zone band plates (proximal / mid / distal) — visual only.
    // 12 cells per zone; each band is two 1×6 strips of the grid.
    const zonePlates = [];
    for (let zone = 0; zone < 3; zone++) {
      const plateGeo = new THREE.PlaneGeometry(3.6, 1.2);
      const plateMat = new THREE.MeshBasicMaterial({
        color: ZONE_TINTS[zone],
        transparent: true,
        opacity: 0.04,
        side: THREE.DoubleSide,
      });
      const plate = new THREE.Mesh(plateGeo, plateMat);
      plate.rotation.x = -Math.PI / 2;
      // Three plates stacked around the grid perimeter
      const angle = (zone / 3) * Math.PI * 2 - Math.PI / 2;
      const r = 3.55;
      plate.position.set(Math.cos(angle) * r, -0.12, Math.sin(angle) * r);
      plate.rotation.z = -angle;
      scene.add(plate);
      zonePlates.push(plate);
    }

    // The 36-cell instanced mesh
    const cellGeo = new THREE.SphereGeometry(0.30, 16, 12);
    const cellMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const instanced = new THREE.InstancedMesh(cellGeo, cellMat, 36);
    instanced.instanceColor = new THREE.InstancedBufferAttribute(
      new Float32Array(36 * 3),
      3
    );

    const dummy = new THREE.Object3D();
    const cellColors = new Float32Array(36 * 3);
    const cellBaseHeights = new Float32Array(36);

    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 6; c++) {
        const idx = r * 6 + c;
        const x = (c - 2.5) * 0.78;
        const z = (r - 2.5) * 0.78;
        dummy.position.set(x, 0.05, z);
        dummy.updateMatrix();
        instanced.setMatrixAt(idx, dummy.matrix);

        const [cr, cg, cb] = kpaToColor(10.0);
        cellColors[idx * 3] = cr;
        cellColors[idx * 3 + 1] = cg;
        cellColors[idx * 3 + 2] = cb;

        cellBaseHeights[idx] = 0.05;
      }
    }
    instanced.instanceMatrix.needsUpdate = true;
    instanced.instanceColor.needsUpdate = true;
    scene.add(instanced);

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 1.0));

    // Subtle scene tilt for depth
    scene.rotation.x = -Math.PI / 9;

    // Track each instance's "current height" so we can tween
    const cellHeights = new Float32Array(36);

    let reqId;
    const animate = () => {
      reqId = requestAnimationFrame(animate);
      const prosthetic = useQuantumStore.getState().prosthetic;
      const cells = prosthetic.cells;
      const phase = prosthetic.cells_phase || "drifted";

      // Highlight zones when a corresponding cell is currently being healed
      const healingFlags = { proximal: false, mid: false, distal: false };
      if (cells && phase === "healing") {
        for (const cell of cells) {
          if (cell.kpa > 12.0) {
            const z = ZONE_LABELS[cell.zone];
            healingFlags[z] = true;
          }
        }
      }
      zonePlates.forEach((plate, zi) => {
        const isHealing = healingFlags[ZONE_LABELS[zi]];
        const targetOpacity = isHealing ? 0.18 : 0.04;
        plate.material.opacity += (targetOpacity - plate.material.opacity) * 0.18;
      });

      // Drive cell colors from cell_state
      for (let i = 0; i < 36; i++) {
        let kpa = 10.0; // neutral
        let targetHeight = 0.05;
        if (cells && cells[i]) {
          kpa = cells[i].kpa;
          // Heavily-drifted cells visibly "pop up" (compartment-syndrome metaphor)
          targetHeight = 0.05 + Math.max(0, kpa - 12) * 0.025;
        }
        cellHeights[i] += (targetHeight - cellHeights[i]) * 0.15;
        dummy.position.set(
          ((i % 6) - 2.5) * 0.78,
          cellHeights[i],
          (Math.floor(i / 6) - 2.5) * 0.78
        );
        dummy.scale.setScalar(1 + Math.max(0, kpa - 18) * 0.02);
        dummy.updateMatrix();
        instanced.setMatrixAt(i, dummy.matrix);

        const [cr, cg, cb] = kpaToColor(kpa);
        cellColors[i * 3] = cr;
        cellColors[i * 3 + 1] = cg;
        cellColors[i * 3 + 2] = cb;
      }
      instanced.instanceMatrix.needsUpdate = true;
      instanced.instanceColor.needsUpdate = true;

      // Live ring color follows global mean
      if (cells) {
        const allKpa = cells.map((c) => c.kpa);
        const mean = allKpa.reduce((a, b) => a + b, 0) / allKpa.length;
        const [mr, mg, mb] = kpaToColor(mean);
        ring.material.color.setRGB(mr, mg, mb);
      }

      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!canvas) return;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(reqId);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      baseGeo.dispose();
      baseMat.dispose();
      ringGeo.dispose();
      ringMat.dispose();
      cellGeo.dispose();
      cellMat.dispose();
      zonePlates.forEach((p) => {
        p.geometry.dispose();
        p.material.dispose();
      });
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full block"
      style={{ minHeight: "260px", display: "block" }}
    />
  );
}
