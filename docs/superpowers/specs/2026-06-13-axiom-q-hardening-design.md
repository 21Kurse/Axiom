# Axiom.Q — Hardening, Real-Data Wiring & Resilience Design

**Date:** 2026-06-13
**Author:** Claude (with user)
**Status:** Draft for review

## Goal

Make `axiom-q` production-shaped for the demo: every byte the UI shows is sourced from the live backend, nothing is faked, no credentials live in source, MongoDB is the single source of truth, the UI shows real errors when something breaks, and the page loads fast via lazy mounting + skeleton placeholders.

## Decisions (from clarifying Qs)

1. **MongoDB**: Local `mongod` on `mongodb://localhost:27017`. Required at backend startup (fail loud with an actionable error). UI surfaces a Mongo connection badge from the `/` health-check.
2. **Qubit config**: Mongo-backed. Backend owns the `qubits` collection; frontend fetches via `GET /api/v1/qubits` on mount. The 8 initial qubits are seeded automatically at first backend startup if the collection is empty.
3. **Fallback policy for LiteLLM**: Delete `vlm_proxy.py`. If LiteLLM is down/times out/returns garbage, propagate the actual exception chain to the frontend. The UI must render the error verbatim in the Agent console — no synthetic correction numbers ever returned to the user.

## In-Scope

### Environment management
- Create `backend/.env` (gitignored) and update `backend/.env.example`. Move:
  - `LITELLM_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL`, `LITELLM_REQUEST_TIMEOUT_SECONDS`
  - `MONGODB_URI`, `MONGODB_DB_NAME`
  - `BACKEND_HOST`, `BACKEND_PORT`, `FRONTEND_ORIGINS` (CORS allowlist)
- Create `axiom-q/.env`, `axiom-q/.env.example`, and Vite env wiring:
  - `VITE_API_BASE_URL` (default `http://localhost:8000`)
  - `VITE_WS_URL` (default `ws://localhost:8000/ws/telemetry`)
- Add `dotenv`/use `python-dotenv` if not loaded already (already covered by importing env vars; need an explicit `load_dotenv()` in `backend/main.py`).
- Update Vite config to read envs via `import.meta.env`.
- Everywhere in code, replace hardcoded URLs/keys with `import.meta.env.*` / `os.getenv(...)`.

### Delete / eliminate static & mock code
- **DELETE** `backend/vlm_proxy.py` (legacy proxy returning `drift_corrected_mhz=-0.142`, `pi_pulse_amp_mod=0.412`, `confidence=0.984`).
- **DELETE** `_make_demo_telemetry()` in `backend/main.py`. If no telemetry exists for a qubit, return `HTTP 409` with `"reason": "no_telemetry_for_qubit"`. The UI renders the error.
- **DELETE** `DEFAULT_CORRECTIONS` fallback dict in `backend/nvidia_client.py`. Errors propagate.
- **DELETE** hardcoded `outcome_fidelity=0.992` in `calibrate_qubit` — compute from current telemetry fidelity ratio instead.
- **DELETE** the `setTimeout`-driven "INGESTING / ANALYZING / CALCULATING" *animation-only* console messages in `useQuantumStore.js`. Keep only logs that respond to a real backend event (websocket arrived, calibration API completed/error, history loaded).
- **DELETE** hardcoded `initialQubits` array in `useQuantumStore.js` (the `frequency: 4.8 + i*0.12`, `amplitude: 0.95 - i*0.02`, `t1_decay: 80 - i*4` defaults). Move all per-qubit state to backend.
- **DELETE** the duplicated `QUBITS` array local to `HardwarePanel.jsx`. Read from store, which fetches from backend.
- **DELETE** the port mismatch — frontend currently connects to `:8001`. Standardize on `8000` (configurable via `VITE_WS_URL`).

### Consolidate Mongo modules
- There are two Mongo files: `backend/db.py` (motor, async) and `backend/database.py` (pymongo, sync, with `_memory_fallback_history`). **Pick one: `db.py` (motor/async).** Move history logging into async functions, drop the in-memory fallback array. Delete `database.py`.

### New / changed data model
Collection `axiom_q.qubits`:
```
{ "_id": "Q0", "label": "Q0", "frequency": 4.8, "amplitude": 0.95, "t1_decay": 80,
  "created_at": "...", "updated_at": "..." }
```
Seed defaults at first backend startup if collection is empty.

Collection `axiom_q.telemetry` (existing — keep schema, just standardized):
```
{ "qubit_id": "Q0", "timestamp": "...", "inputs": {...}, "raw_counts": [...],
  "probabilities": [...], "status": "UNCALIBRATED" | "CALIBRATED",
  "calibration": { "corrections": {...}, "confidence": 0.0, "outcome_fidelity": 0.0,
                   "calibrated_at": "..." } }
```

Collection `axiom_q.calibration_history`:
```
{ "qubit_id": "Q0", "timestamp": "...", "noise_parameters": {...},
  "raw_waveform_summary": {"points": N, "min": ..., "max": ...},
  "vlm_json_response": {...}, "outcome_fidelity": ...,
  "model": "ising-calibration", "status": "SUCCESS" | "ERROR",
  "error_detail": null | {...} }
```

### New / changed API surface
| Method | Path | Behavior |
|---|---|---|
| GET | `/` | Health: `{status, mongo, litellm_ping, litellm_reachable}` — frontend drives the readiness badge |
| GET | `/api/v1/qubits` | Returns seeded qubit configs |
| POST | `/api/v1/qubits/{id}/ping` | Optional: send a single Rabi-step and stream 1 message back (live-wire test) |
| POST | `/api/v1/calibrate/{qubit_id}` | Returns `{status, qubit_id, corrections, confidence, outcome_fidelity, calibrated_at, source}`. On error: `{status:"ERROR", reason, detail}`. |
| GET | `/api/v1/telemetry/{qubit_id}?limit=N` | Recent telemetry history for the timeline |
| GET | `/api/v1/history` | Recent calibration runs |
| WS | `/ws/telemetry` | Bidirectional telemetry; errors include the JSON parser/Simulator/LiteLLM exception text |

### Resilience — error surfacing
- All API routes return `{status:"SUCCESS"|"ERROR", ...}` with the **actual exception text** (sanitized).
- WS messages always carry `event` + payload or `event:"error"` with the exception chain.
- Frontend: in `useQuantumStore`, every action that calls the API stores the raw error in `ai_console_logs` AND renders it in a top-level error toast (`ErrorBoundary`), so users can see exactly what failed (DNS refused, LiteLLM timeout, simulator crash, schema mismatch, etc.).

### Performance — lazy loading + skeletons
- Wrap each panel in `React.lazy` (`HardwarePanel`, `TelemetryPanel`, `AgentPanel`) and mount via `<Suspense fallback={<SkeletonPanel/>}>`.
- BlochSphere (Three.js, ~500KB) lazy-import only when the user opens the panel or after first paint.
- Recharts already lazy via panel loading.
- Skeletons (CSS-only, animated shimmer):
  - `SkeletonPanel` re-used for any panel before its real JS resolves
  - `SkeletonChart` placeholder for telemetry chart while first telemetry WS frame is pending
  - `SkeletonRow` for calibration history list
- Bundle splitting preview: `npm run build` should produce ≥3 chunks (vendor / three / app).

### MongoDB Compass setup
Provide a one-shot script `backend/scripts/seed_qubits.py` and document:
```
# Start mongod locally, then:
mongosh "mongodb://localhost:27017" axiom_q < backend/scripts/seed_qubits.js
# Or just launch the backend — it self-seeds if the qubits collection is empty.
```
Also document the MongoDB VS Code extension connection string the user needs to paste (`mongodb://localhost:27017`, db `axiom_q`).

### Backend dependency update
Add `python-dotenv>=1.0.0` to `requirements.txt`. Remove `pymongo` if not used directly (motor wraps it — keep motor only).

## Non-Goals (YAGNI)
- Auth / multi-user.
- Persistent LiteLLM queueing / retry with backoff (we surface the error, user retries).
- Schema migrations beyond the initial seed.
- Production deployment configuration.

## Risks & Mitigations
- **Mongo hard-dependency** at backend startup could be too strict for the user's local setup. Mitigation: log a loud `ERROR` with `pymongo.errors.ServerSelectionTimeoutError` printed in full; the process exits with non-zero. The UI shows a MongoDB-down banner until backend comes back up.
- **LiteLLM availability** is outside our control. Documenting the readiness check (a 5s GET to `/health` of LiteLLM) gives the UI a hint; the calibrate API still surfaces a real error.
- **Vite env vars are public** — fine for an internal demo. Note in README that production should not ship `VITE_LITELLM_*`.

## File-Level Change List
- New: `backend/scripts/seed_qubits.py` (or self-seed in startup)
- New: `axiom-q/.env.example`
- Modified: `backend/main.py` (delete `_make_demo_telemetry`, add startup/shutdown for Mongo, env loading, real error responses, qubit API)
- Modified: `backend/nvidia_client.py` (remove `DEFAULT_CORRECTIONS`, surface errors, simpler async flow)
- Modified: `backend/db.py` (add qubit collection helpers; add ping endpoint; lifespan-managed client)
- Modified: `backend/requirements.txt` (add `python-dotenv`, ensure `pymongo` is dropped)
- Modified: `backend/.env.example` (full env list)
- Modified: `axiom-q/src/store/useQuantumStore.js` (no hardcoded qubits; API-driven; real error state)
- Modified: `axiom-q/src/components/*` (lazy imports, skeleton wrappers, no fallback data)
- Modified: `axiom-q/src/main.jsx` / `App.jsx` (Suspense boundaries, error boundary)
- Modified: `axiom-q/.gitignore` (add `.env`, not just `.env.example`)
- Modified: `axiom-q/vite.config.js` (env typing optional; expose envs)
- New: `axiom-q/src/components/ui/Skeleton.jsx`
- New: `axiom-q/src/components/ui/ErrorBoundary.jsx`
- New: `axiom-q/src/components/ui/StatusBar.jsx` (Mongo/Backend ready indicators)
- Deleted: `backend/vlm_proxy.py`, `backend/database.py`

## Acceptance Criteria
- [ ] Running the backend before starting MongoDB exits with a clear error.
- [ ] Running the backend after MongoDB automatically seeds the 8 qubits and serves them.
- [ ] Frontend gets the qubit list from the API; no hardcoded array remains in source.
- [ ] Calibrate endpoint returns the actual `drift_corrected_mhz`, `pi_pulse_amp_mod`, `confidence` from LiteLLM — when reachable — or the verbatim error reason when not.
- [ ] No `drift_corrected_mhz=-0.142` synthetic value appears in any response anywhere.
- [ ] Every API and WS error appears verbatim in the Agent console with timestamps.
- [ ] Frontend `npm run build` produces multiple JS chunks (`three` separated out).
- [ ] Page first paint shows skeleton panels <100ms after JS load; resolved panels fade in.
- [ ] `.env` files are present at both backend and frontend; `.env` is gitignored; `.env.example` documents required keys.
- [ ] Test plan: spin down LiteLLM → click "Run Autonomous Calibration" → see `URLError: [Errno 111] Connection refused` in the console.

---
**End of design.** Will write implementation plan in `writing-plans` next step, then execute.
