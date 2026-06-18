# QVis Quantum Prosthetic — Vertical Slice Plan (v2)

**Date:** 2026-06-13
**Owner:** Abhay / Eloise / Team
**Branch:** `temp` (already merges `prosthetics` per `72d4b26`)
**Demo target:** 30-second sequence — judge drags an on-screen potentiometer → heatmap drifts red → NVIDIA VLM diagnoses → Three.js prosthetic-socket mesh colors flip back to green cell-by-cell.

> **Pivot from v1** (2026-06-13 14:00): the user clarified the demo
> is **all-virtual** — no Arduino / no servos on the table. The
> "prosthetic" is a conceptual/visual story driving a KiCad-style
> **PCB/socket simulation** rendered via Three.js triangle meshes.
> The physical hardware list (Arduino, Pi, MCP3008, 3 servos)
> belongs to a *future production vision*, not the 12-hour slice.

---

## Architecture (decided)

```text
┌──────────────────┐  WS (slider values)    ┌────────────────────┐
│ Judge's finger   │ ────────────────────►  │  backend.main   │
│  drags soft      │ ◄──────────── WS ───  │  :8000              │
│  potentiometer   │   (mesh color updates) │                      │
│  in the HUD      │                        │                      │
└──────────────────┘                        │                      │
                                            │  ┌────────────┐    │
                                            │  │ telemetry  │    │
                                            │  │  inject_   │    │
                                            │  │  drift(pot)│    │
                                            │  └─────┬──────┘    │
                                            │        ▼             │
                                            │  ┌────────────┐    │
                                            │  │ heatmap.png│──► │  LiteLLM
                                            │  │ (side-by-s)│    │  → NVIDIA
                                            │  └─────┬──────┘    │  VLM
                                            │        ▼             │
                                            │  ┌────────────┐    │
                                            │  │ agent.anlyz│    │
                                            │  └─────┬──────┘    │
                                            │        ▼             │
                                            │  ┌────────────┐    │
                                            │  │ healing    │──► │ MongoDB
                                            │  │ broadcast  │    │ ledger
                                            │  └────────────┘    │
                                            └────────────────────┘
                                                            │
                                                            ▼
                                            ┌────────────────────┐
                                            │  React HUD          │
                                            │  TelemetryPanel     │
                                            │  ┌──────────────┐   │
                                            │  │ Three.js mesh │   │  ← existing
                                            │  │ 36-cell       │   │     three dep
                                            │  │ socket        │   │
                                            │  └──────────────┘   │
                                            └────────────────────┘
```

- **Soft potentiometer** (React-draggable slider styled like a knob) → WS event → backend.
- **Backend** runs telemetry → heatmap → VLM → healing → ledger, **with drift severity scaled by the pot value**.
- **HUD** uses the same `three` dep already in `package.json` (`^0.184.0`) to render a 36-cell prosthetic-socket mesh. Cell colors tween on drift + heal.
- Mesh groups (proximal / mid / distal) preserve the `(row+col) % 3` zone dispatch — visual only — so the VLM's per-cell corrections land in one of 3 mesh animations.

### 3-zone mesh dispatching

The VLM agent returns corrections as `{"cell_id": "23", "target_kpa": 8.0}` — a grid coordinate, **not** a mesh group. The Python bridge maps each cell to one of three mesh groups using `(row + col) % 3`:

| Zone | Mesh group label  | Cells (12 each)                       |
| ---- | ----------------- | ------------------------------------- |
| 0    | proximal band     | (0,0)(0,3)(1,2)(1,5)(2,1)(2,4) + 6   |
| 1    | mid band          | (0,1)(0,4)(1,0)(1,3)(2,2)(2,5) + 6   |
| 2    | distal band       | (0,2)(0,5)(1,1)(1,4)(2,0)(2,3) + 6   |

Concept preserved from v1; only the **output target** changed from a servo to a mesh material/position tween.

---

## 12-hour hour-by-hour plan

### H0–H1 — Input scaffold + plan rewrite (DONE in part)

- ✅ Spec doc reflects all-virtual + Three.js direction (this file).
- ✅ Project memory updated.
- ✅ Existing [arduino_demo.ino](axiom-q/backend/prosthetics/arduino_demo/arduino_demo.ino) and [arduino_io.py](axiom-q/backend/prosthetics/arduino_io.py) deprecated, marked for deletion post-confirmation.

### H1–H2 — Pot-driven drift + slider component

- Refactor `telemetry.inject_drift()` to accept `pot_value: float ∈ [0, 1]`. Scales:
  - `drift_factor_max` ∈ [1.30, 1.60] linearly by pot
  - `drift_cell_count` ∈ [3, 12] by pot
- New React component [ProstheticPot.tsx](axiom-q/src/components/ProstheticPot.jsx): styled as a knob with a tick scale (0–100 %). WS-emits on drag.
- WebSocket endpoint `WS /ws/pot` on backend, emits frames `{value, ts}` at ~30 Hz.

### H2–H3 — Three.js 36-cell socket mesh

- New component [ProstheticMesh.jsx](axiom-q/src/components/ProstheticMesh.jsx):
  - 6×6 instanced `<mesh>` of small spheres or rounded boxes (one per cell)
  - Per-instance color uniform driven from backend cell-state payload
  - Smooth tween between drifted (red) ↔ healed (green) at ~250 ms per cell
  - Three-zone coloring highlight when a correction fires (proximal/mid/distal)

### H3–H4 — Wire the live loop

- `main.run_live_demo(pot_input, ws_broadcast)` — when pot crosses 0.30 (rising edge), synchronously:
  1. Run Qiskit drift scaled by pot
  2. Render heatmap.png (sent to VLM as base64)
  3. VLM diagnose → corrections
  4. Apply healing → broadcast cell state over WS to mesh
  5. Record to MongoDB
- Demo must complete in ≤ 25 seconds end-to-end.

### H4–H5 — Live HUD

- Extend [TelemetryPanel.jsx](axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx) to host:
  - the ProstheticPot knob (left)
  - the ProstheticMesh (center, replacing the Bloch sphere for this view, or in a new tab)
  - a JSON inspector (right) reusing the existing terminal style
- Status states: `READY → DRIFT INJECTED → DIAGNOSING → HEALING → READY`, with neon badge color from design-spec.md.

### H5–H6 — E2E in browser

- Run `npm run dev` + `uvicorn backend.main:app --reload`, drag the pot to 0.45, watch all 5 phases cycle, verify ledger row appears in MongoDB Comfort History.

### H6–H7 — Demo polish + insurance video

- Record 30-second screen capture
- Caption: "Axiom-Q Prosthetic Slice — VLM-Driven Quantum-Calibrated Self-Healing Limb Socket"
- Update [README.md](axiom-q/README.md) with a "vertical slice" section

### H7–H8 — Buffer

- Reserve for hackathon pivots.

---

## Files to create / modify (no surprises)

| Status     | Path                                                                              | What                                                              |
| ---------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Delete     | `axiom-q/backend/prosthetics/arduino_demo/arduino_demo.ino`                       | No hardware                                                       |
| Delete     | `axiom-q/backend/prosthetics/arduino_io.py`                                       | No hardware                                                       |
| Delete     | `axiom-q/backend/prosthetics/HARDWARE_SETUP.md`                                   | No hardware                                                       |
| Modify     | `axiom-q/backend/prosthetics/telemetry.py`                                        | `inject_drift(target, pot_value)` scales Qiskit drift by knob     |
| Modify     | `axiom-q/backend/prosthetics/healing.py`                                          | Replace `send_to_arduino` with `broadcast_to_ws`                  |
| Modify     | `axiom-q/backend/prosthetics/main.py`                                             | Add `run_live_demo(ws)` + `argparse --mode {live,replay,oneshot}` |
| Modify     | `axiom-q/backend/prosthetics/ledger.py`                                           | Unchanged behavior, possibly tag entries with `pot_value`         |
| Modify     | `axiom-q/backend/main.py`                                                         | Add `/ws/pot` slider WebSocket endpoint                           |
| Create     | `axiom-q/src/components/ProstheticPot/ProstheticPot.jsx`                          | Knob UI control styled per design-spec.md                         |
| Create     | `axiom-q/src/components/ProstheticMesh/ProstheticMesh.jsx`                        | Three.js 36-cell mesh                                             |
| Modify     | `axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx`                        | Add pot + mesh + status badge                                     |
| Create     | `docs/superpowers/specs/2026-06-13-prosthetics-slice-plan-v2.md`                  | **This file**                                                     |

---

## Risks

1. **VLM latency:** LiteLLM is ~5 s. 30-second budget is fine, but we must show a "DIAGNOSING…" state badge to absorb judge-attention pressure.
2. **WebSocket backpressure:** if pot drags faster than backend can drain, frames stack up. Cap at 30 Hz on the frontend; drop on the backend if it falls behind.
3. **Wallet hookup:** backend WS broadcast should fit within FastAPI's `asyncio` task granularity; one queue per connected client.
4. **Three.js material tween:** per-instance color uniform is cheap (~36 floats), but a 250 ms tween per cell across 12 simultaneously-corrected cells can stutter on integrated GPUs. Use `MeshBasicMaterial` (no normal/light computation) and a single shared `BufferGeometry` with per-instance attributes.
5. **MongoDB on the demo loop:** every cycle hitting Mongo can lag. Batch writes or use `insertOne` async fire-and-forget on the happy path.
6. **Demo seed:** always default to `seed=42` for replays so judge-time glitches are recoverable.

---

## Acceptance criteria

A judge who walks up to the table sees:

1. A **soft potentiometer knob** styled in the dark cyberpunk palette.
2. Judge **drags the knob to 45 %**.
3. Within **1 second**, the **Three.js prosthetic mesh** reddens in scattered cells (Qiskit drift pattern).
4. Within **2 seconds** of that, a `heatmap_noisy.png` is rendered and shown in the HUD.
5. Within **5 seconds** of that, the NVIDIA VLM diagnosis JSON appears in the inspector pane.
6. Within **2 seconds** of that, the **mesh animates back to green** cell-by-cell over ~3 seconds, in 3 zone groups (proximal / mid / distal).
7. **MongoDB Comfort History** gains a new row tagged with the pot value.
8. Total elapsed: **20–25 seconds**, reproducible with `--demo --seed 42`.
