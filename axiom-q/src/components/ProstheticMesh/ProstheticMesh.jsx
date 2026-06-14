import { useEffect, useRef } from "react";
import * as THREE from "three";
import useQuantumStore from "../../store/useQuantumStore";


/* ── Color ramp: emerald green (healthy) → amber (warning) → red (danger) ─── */
function kpaToColor(kpa) {
 // Maps directly to the RYG colormap of the heatmap (8..30 kPa)
 const stops = [
   { k: 8.0,  c: [0.06, 0.73, 0.51] },  // nominal green (emerald)
   { k: 12.0, c: [0.06, 0.73, 0.51] },  // nominal green
   { k: 15.0, c: [0.96, 0.62, 0.04] },  // caution yellow/orange
   { k: 18.0, c: [0.94, 0.27, 0.27] },  // red
   { k: 30.0, c: [0.75, 0.15, 0.15] },  // deep crimson danger
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
const ZONE_TINTS = [0xb8b0c0, 0xb0b8c0, 0xb8c0b0];


/**
* 36-cell Three.js rectangular prosthetic mesh.
*
* Each cell is a rectangular box shaped InstancedMesh colored by the latest
* ``cells[].kpa`` value from /ws/prosthetic.
*
* It responds to real-time pointer drags by previewing drift before the
* calibration cycle is fired.
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


   // Rectangular limb-socket backdrop plate under the grid
   const baseGeo = new THREE.BoxGeometry(4.8, 0.4, 4.8);
   const baseMat = new THREE.MeshStandardMaterial({
     color: 0x15151b,
     roughness: 0.8,
     metalness: 0.2,
     transparent: true,
     opacity: 0.9,
   });
   const base = new THREE.Mesh(baseGeo, baseMat);
   base.position.y = -0.32;
   scene.add(base);


   // Rectangular border outline
   const borderGeo = new THREE.BoxGeometry(4.65, 0.05, 4.65);
   const borderMat = new THREE.MeshBasicMaterial({
     color: 0xb0b8c4,
     transparent: true,
     opacity: 0.2,
     wireframe: true,
   });
   const border = new THREE.Mesh(borderGeo, borderMat);
   border.position.y = -0.13;
   scene.add(border);


   // 3-zone band plates (proximal / mid / distal) aligned as rectangular stripes
   const zonePlates = [];
   for (let zone = 0; zone < 3; zone++) {
     const plateGeo = new THREE.PlaneGeometry(4.4, 1.35);
     const plateMat = new THREE.MeshBasicMaterial({
       color: ZONE_TINTS[zone],
       transparent: true,
       opacity: 0.04,
       side: THREE.DoubleSide,
     });
     const plate = new THREE.Mesh(plateGeo, plateMat);
     plate.rotation.x = -Math.PI / 2;
     plate.position.set(0, -0.12, (zone - 1) * 1.5);
     scene.add(plate);
     zonePlates.push(plate);
   }


   // Rectangular cells instanced mesh (BoxGeometry instead of SphereGeometry)
   const cellGeo = new THREE.BoxGeometry(0.68, 0.30, 0.68);
   const cellMat = new THREE.MeshStandardMaterial({
     roughness: 0.3,
     metalness: 0.1,
   });
   const instanced = new THREE.InstancedMesh(cellGeo, cellMat, 36);
   instanced.instanceColor = new THREE.InstancedBufferAttribute(
     new Float32Array(36 * 3),
     3
   );


   const dummy = new THREE.Object3D();
   const tempColor = new THREE.Color();
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
       tempColor.setRGB(cr, cg, cb);
       instanced.setColorAt(idx, tempColor);


       cellBaseHeights[idx] = 0.05;
     }
   }
   instanced.instanceMatrix.needsUpdate = true;
   instanced.instanceColor.needsUpdate = true;
   scene.add(instanced);


   // Premium Directional + Ambient Lighting
   scene.add(new THREE.AmbientLight(0xffffff, 0.6));
   const dirLight = new THREE.DirectionalLight(0xffffff, 0.9);
   dirLight.position.set(5, 12, 8);
   scene.add(dirLight);


   // Subtle scene tilt for depth
   scene.rotation.x = -Math.PI / 9;


   // Track heights for tweening
   const cellHeights = new Float32Array(36);


   let reqId;
   const animate = () => {
     reqId = requestAnimationFrame(animate);
     const state = useQuantumStore.getState();
     const prosthetic = state.prosthetic;
     const cells = prosthetic.cells;
     const phase = prosthetic.cells_phase || "drifted";


     // Highlight zones when corresponding cells are active in healing phase
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


     // Drive cell colors & height scale from active states
     for (let i = 0; i < 36; i++) {
       let kpa = 10.0;
       let targetHeight = 0.05;


       if (cells && cells[i]) {
         kpa = cells[i].kpa;
         // Heavily-drifted cells pop up (pressure swelling representation)
         targetHeight = 0.05 + Math.max(0, kpa - 12) * 0.045;
       } else if (prosthetic.pot_value > 0 && !prosthetic.cycle_running) {
         // Continuous slider-drag preview: dynamically grow pressure cells
         const seedIndex = (i * 17) % 36;
         const isDrifting = seedIndex < Math.round(prosthetic.pot_value * 12);
         if (isDrifting) {
           kpa = 10.0 + prosthetic.pot_value * 14.0;
           targetHeight = 0.05 + Math.max(0, kpa - 12) * 0.045;
         }
       }


       cellHeights[i] += (targetHeight - cellHeights[i]) * 0.15;
       dummy.position.set(
         ((i % 6) - 2.5) * 0.78,
         cellHeights[i],
         (Math.floor(i / 6) - 2.5) * 0.78
       );
       // Box scaling: scales slightly in all axes for visual impact under load
       dummy.scale.set(
         1 + Math.max(0, kpa - 12) * 0.015,
         1 + Math.max(0, kpa - 12) * 0.06,
         1 + Math.max(0, kpa - 12) * 0.015
       );
       dummy.updateMatrix();
       instanced.setMatrixAt(i, dummy.matrix);


       // Fetch colors matching green-yellow-red warning model
       let [cr, cg, cb] = kpaToColor(kpa);


       // Calibration visual effect
       if (phase === "healing" && kpa > 10.5) {
          // Mix with a bright integrated calibration color (cyan/blue)
          const pulse = (Math.sin(Date.now() * 0.008 + i) * 0.5 + 0.5) * 0.7;
          cr = cr * (1 - pulse) + 0.1 * pulse;
          cg = cg * (1 - pulse) + 0.8 * pulse;
          cb = cb * (1 - pulse) + 1.0 * pulse;
       }


       tempColor.setRGB(cr, cg, cb);
       instanced.setColorAt(i, tempColor);
     }
     instanced.instanceMatrix.needsUpdate = true;
     instanced.instanceColor.needsUpdate = true;


     // Update base border color to match overall average grid load
     if (cells) {
       const allKpa = cells.map((c) => c.kpa);
       const mean = allKpa.reduce((a, b) => a + b, 0) / allKpa.length;
       const [mr, mg, mb] = kpaToColor(mean);
       border.material.color.setRGB(mr, mg, mb);
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
     borderGeo.dispose();
     borderMat.dispose();
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



