# Axiom.Q Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make axiom-q fully dynamic — no mocks, no hardcoded data, MongoDB-backed, env-configured, with real error surfacing and lazy-loaded skeleton UI.

**Architecture:** Backend (FastAPI) owns all state via MongoDB (motor async). Frontend (React/Vite) fetches everything from API — zero static arrays. Errors propagate end-to-end verbatim. Panels are lazy-loaded with shimmer skeletons.

**Tech Stack:** FastAPI, motor (pymongo async), python-dotenv, qiskit-aer, React 19, Zustand, Vite, Three.js, Recharts, Tailwind CSS 4

---

## File Structure

### New Files
- `axiom-q/.env.example` — Frontend env template
- `axiom-q/.env` — Frontend env (gitignored)
- `axiom-q/src/components/ui/Skeleton.jsx` — Skeleton components
- `axiom-q/src/components/ui/ErrorBoundary.jsx` — Error boundary wrapper
- `axiom-q/src/components/ui/StatusBar.jsx` — Backend/Mongo/LiteLLM readiness bar

### Modified Files
- `axiom-q/.gitignore` — Add `.env` entries
- `axiom-q/vite.config.js` — No change needed (Vite auto-exposes VITE_* env)
- `axiom-q/src/main.jsx` — Wrap app in ErrorBoundary
- `axiom-q/src/App.jsx` — Lazy imports + Suspense for panels
- `axiom-q/src/store/useQuantumStore.js` — Replace hardcoded qubits with API fetch, fix WS URL, remove fake logs, add error state
- `axiom-q/src/components/HardwarePanel/HardwarePanel.jsx` — Remove local QUBITS array, read from store
- `axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx` — Add skeleton for chart while awaiting data
- `axiom-q/src/components/AgentPanel/AgentPanel.jsx` — Render real errors, no fake messages
- `axiom-q/src/components/Header/Header.jsx` — Import StatusBar
- `axiom-q/backend/.env.example` — Expanded with all env vars
- `axiom-q/backend/.env` — Actual env values (gitignored)
- `axiom-q/backend/requirements.txt` — Add python-dotenv, remove direct pymongo if only motor uses it
- `axiom-q/backend/main.py` — Remove `_make_demo_telemetry`, add `load_dotenv()`, add startup event for Mongo ping + seed, add `/api/v1/qubits`, fix error responses, remove hardcoded fidelity
- `axiom-q/backend/db.py` — Add qubit collection helpers, startup-managed motor client, remove in-memory fallback
- `axiom-q/backend/nvidia_client.py` — Remove `DEFAULT_CORRECTIONS`, propagate errors
- `axiom-q/backend/telemetry_store.py` — No structural change (in-memory cache stays as hot layer)

### Deleted Files
- `axiom-q/backend/vlm_proxy.py` — Remove legacy mock proxy
- `axiom-q/backend/database.py` — Consolidate into `db.py`

---

## Task 1: Environment Files — Backend

**Files:**
- Modify: `axiom-q/backend/.env.example`
- Create: `axiom-q/backend/.env`
- Modify: `axiom-q/backend/requirements.txt`
- Modify: `axiom-q/backend/main.py` (add `load_dotenv()`)

- [ ] **Step 1: Update `backend/.env.example` with full variable list**

Write the file:

```
# ── MongoDB ──
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=axiom_q

# ── LiteLLM proxy (OpenAI-compatible) ──
LITELLM_URL=http://127.0.0.1:4000/v1/chat/completions
LITELLM_API_KEY=freecc
LITELLM_MODEL=ising-calibration
LITELLM_REQUEST_TIMEOUT_SECONDS=60

# ── Backend server ──
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# ── CORS ──
FRONTEND_ORIGINS=http://localhost:5173,http://localhost:4173
```

- [ ] **Step 2: Create `backend/.env` with same defaults (copy of .env.example)**

Copy the same content into `.env`. This is the file the server reads at runtime.

- [ ] **Step 3: Add `python-dotenv` to `backend/requirements.txt`**

```
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
qiskit>=1.0.2
qiskit-aer>=0.14.0
motor>=3.3.2
numpy>=1.26.0
python-dotenv>=1.0.0
```

- [ ] **Step 4: Add `load_dotenv()` to `backend/main.py` top**

Add at the very top of the file, before any other imports:

```python
from dotenv import load_dotenv
load_dotenv()
```

- [ ] **Step 5: Replace hardcoded values in `backend/main.py` with env vars**

Change the uvicorn block at bottom:

```python
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
```

Also replace `allow_origins=["*"]` with:

```python
_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 6: Update `backend/nvidia_client.py` to read env from .env (already does via os.getenv — no change needed, just verify the keys match `.env.example`)**

Verify the existing `os.getenv` calls in `nvidia_client.py` match the variable names in `.env.example`. They do.

- [ ] **Step 7: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/backend/.env.example axiom-q/backend/.env axiom-q/backend/requirements.txt axiom-q/backend/main.py axiom-q/backend/nvidia_client.py
git commit -m "feat(env): backend env files with dotenv, full variable list"
```

---

## Task 2: Environment Files — Frontend

**Files:**
- Create: `axiom-q/.env.example`
- Create: `axiom-q/.env`
- Modify: `axiom-q/.gitignore`

- [ ] **Step 1: Create `axiom-q/.env.example`**

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/telemetry
```

- [ ] **Step 2: Create `axiom-q/.env`** (same content as .env.example)

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/telemetry
```

- [ ] **Step 3: Update `axiom-q/.gitignore` — add .env protection**

Add these lines after `*.local`:

```
# Environment files
.env
.env.local
```

- [ ] **Step 4: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/.env.example axiom-q/.env axiom-q/.gitignore
git commit -m "feat(env): frontend env files with VITE_API_BASE_URL and VITE_WS_URL"
```

---

## Task 3: Delete Mock/Static Backend Code

**Files:**
- Delete: `axiom-q/backend/vlm_proxy.py`
- Delete: `axiom-q/backend/database.py`
- Modify: `axiom-q/backend/main.py`
- Modify: `axiom-q/backend/nvidia_client.py`

- [ ] **Step 1: Delete `backend/vlm_proxy.py`**

Delete the entire file. It was a mock server returning hardcoded `drift_corrected_mhz=-0.142`, `pi_pulse_amp_mod=0.412`, `confidence=0.984`.

- [ ] **Step 2: Delete `backend/database.py`**

Delete the entire file. Its functionality (history logging) will move into `db.py` in Task 4.

- [ ] **Step 3: Remove `_make_demo_telemetry()` from `backend/main.py`**

Delete the function definition (lines ~125-141) and update `calibrate_qubit` to return an error instead of generating fake data:

In `calibrate_qubit`, replace:
```python
    # 3) Otherwise use a synthetic Rabi curve so the calibration can still run.
    if not doc:
        log.info("No telemetry for %s; using demo Rabi curve.", qubit_id)
        doc = _make_demo_telemetry(qubit_id)
```

With:
```python
    if not doc:
        return {"status": "ERROR", "qubit_id": qubit_id, "reason": "no_telemetry_for_qubit",
                "detail": f"No telemetry data available for qubit {qubit_id}. Send noise parameters via the telemetry WebSocket first."}
```

Also delete the `_probs_from_raw_counts` helper if no longer referenced (it still is used as a fallback in the calibrate function — keep it for the case where doc has `raw_counts` but no `probabilities`).

- [ ] **Step 4: Remove `DEFAULT_CORRECTIONS` from `backend/nvidia_client.py`**

Delete the dict:
```python
DEFAULT_CORRECTIONS = {
    "drift_corrected_mhz": -0.142,
    "pi_pulse_amp_mod": 0.412,
    "confidence": 0.984
}
```

Update `call_nvidia_ising_model` to propagate errors instead of returning fallback:

```python
async def call_nvidia_ising_model(qubit_id: str, probabilities: list, noise_inputs: dict) -> dict:
    prompt = _build_calibration_prompt(qubit_id, probabilities, noise_inputs)

    loop = asyncio.get_running_loop()
    raw_response = await loop.run_in_executor(None, _call_litellm_sync, prompt)
    result = _parse_model_response(raw_response)
    log.info("NVIDIA Ising model returned: %s", result)
    return result
```

No try/except here — let the exception bubble up to `calibrate_qubit` which catches it:

In `main.py` `calibrate_qubit`, wrap the call:

```python
    try:
        vlm_data = await call_nvidia_ising_model(qubit_id, probs, inputs)
    except Exception as e:
        log.exception("LiteLLM call failed for %s: %s", qubit_id, e)
        return {"status": "ERROR", "qubit_id": qubit_id, "reason": "litellm_error",
                "detail": str(e)}
```

- [ ] **Step 5: Remove hardcoded `outcome_fidelity=0.992` in `calibrate_qubit`**

Replace the log_calibration_run call. Compute fidelity from telemetry:

```python
    # Compute outcome fidelity from calibration results
    outcome_fidelity = float(confidence) if confidence else 0.0
```

- [ ] **Step 6: Remove the `from backend.database import ...` import in `main.py`**

Delete:
```python
from backend.database import log_calibration_run, get_recent_history
```

These will be replaced with `db.` calls after Task 4.

- [ ] **Step 7: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/backend/
git commit -m "feat: delete vlm_proxy.py, database.py, remove demo telemetry and DEFAULT_CORRECTIONS fallbacks"
```

---

## Task 4: Consolidate MongoDB into `db.py` (motor async)

**Files:**
- Rewrite: `axiom-q/backend/db.py`
- Modify: `axiom-q/backend/main.py` (use new `db.` functions)

- [ ] **Step 1: Rewrite `backend/db.py` as single async Mongo module**

Replace entire content with:

```python
"""
Single async MongoDB module for axiom-q (motor).
Lifespan-managed client; seeded on startup.
"""

import os
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

log = logging.getLogger("axiom-q.db")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "axiom_q")

_client: AsyncIOMotorClient | None = None
_db = None
telemetry_col = None
qubits_col = None
history_col = None


async def startup():
    """Connect and verify MongoDB. Raises on failure (so FastAPI lifespan can surface it)."""
    global _client, _db, telemetry_col, qubits_col, history_col
    _client = AsyncIOMotorClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
    )
    # Force a ping to verify connection
    await _client.admin.command("ping")
    _db = _client[MONGODB_DB_NAME]
    telemetry_col = _db.telemetry
    qubits_col = _db.qubits
    history_col = _db.calibration_history

    log.info("MongoDB connected at %s (db=%s)", MONGODB_URI, MONGODB_DB_NAME)

    # Auto-seed qubits if collection is empty
    count = await qubits_col.count_documents({})
    if count == 0:
        log.info("Qubits collection empty — seeding defaults...")
        defaults = _default_qubits()
        await qubits_col.insert_many(defaults)
        log.info("Seeded %d qubits.", len(defaults))


async def shutdown():
    """Close the motor client gracefully."""
    global _client
    if _client:
        _client.close()
        log.info("MongoDB client closed.")


def is_available() -> bool:
    """Non-async check: has the client talked to a server?"""
    if _client is None:
        return False
    try:
        return bool(_client.nodes)
    except Exception:
        return False


def _default_qubits() -> list[dict]:
    """8-qubit register defaults matching the original hardcoded values."""
    qubits = []
    for i in range(8):
        qubits.append({
            "_id": f"Q{i}",
            "label": f"Q{i}",
            "frequency": round(4.8 + i * 0.12, 2),
            "amplitude": round(0.95 - i * 0.02, 3),
            "t1_decay": 80 - i * 4,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    return qubits


# ── Qubit helpers ──

async def get_all_qubits() -> list[dict]:
    if not is_available():
        return []
    cursor = qubits_col.find({}, {"_id": 0})
    return await cursor.to_list(length=100)


async def get_qubit(qubit_id: str) -> dict | None:
    if not is_available():
        return None
    return await qubits_col.find_one({"_id": qubit_id}, {"_id": 0})


# ── Telemetry helpers ──

async def insert_telemetry(record: dict) -> None:
    if not is_available():
        return
    try:
        await telemetry_col.insert_one(record)
    except Exception as e:
        log.warning("Mongo telemetry insert skipped: %s", e)


async def get_latest_uncalibrated_telemetry(qubit_id: str):
    if not is_available():
        return None
    try:
        return await telemetry_col.find_one(
            {"qubit_id": qubit_id, "status": "UNCALIBRATED"},
            sort=[("timestamp", -1)],
        )
    except Exception as e:
        log.warning("Mongo telemetry query skipped: %s", e)
        return None


async def update_telemetry_status(doc_id, status: str, corrections: dict = None) -> None:
    if not is_available():
        return
    try:
        update_doc = {"status": status}
        if corrections:
            update_doc["corrections"] = corrections
        await telemetry_col.update_one({"_id": doc_id}, {"$set": update_doc})
    except Exception as e:
        log.warning("Mongo telemetry update skipped: %s", e)


# ── Calibration history helpers ──

async def log_calibration_run(
    qubit_id: str,
    noise_parameters: dict,
    raw_waveform_data: list,
    vlm_json_response: dict,
    outcome_fidelity: float,
    status: str = "SUCCESS",
    error_detail: str | None = None,
):
    if not is_available():
        return
    try:
        # Store a summary rather than the full waveform to keep docs small
        summary = {}
        if raw_waveform_data:
            probs = [c.get("1", 0) / sum(c.values()) if sum(c.values()) > 0 else 0 for c in raw_waveform_data]
            summary = {"points": len(probs), "min": min(probs) if probs else 0, "max": max(probs) if probs else 0}

        entry = {
            "qubit_id": qubit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "noise_parameters": noise_parameters,
            "raw_waveform_summary": summary,
            "vlm_json_response": vlm_json_response,
            "outcome_fidelity": outcome_fidelity,
            "model": os.getenv("LITELLM_MODEL", "ising-calibration"),
            "status": status,
            "error_detail": error_detail,
        }
        await history_col.insert_one(entry)
    except Exception as e:
        log.warning("Mongo calibration log skipped: %s", e)


async def get_recent_history(limit: int = 5):
    if not is_available():
        return []
    try:
        cursor = history_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception as e:
        log.warning("Mongo history query skipped: %s", e)
        return []
```

- [ ] **Step 2: Update `backend/main.py` to use the new `db` module**

Replace the old `from backend.database import ...` with the async `db.` calls:

At top of `main.py`, replace:
```python
from backend import db
from backend import telemetry_store
from backend.database import log_calibration_run, get_recent_history
```

With:
```python
from backend import db
from backend import telemetry_store
```

Add a lifespan context manager for startup/shutdown:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.startup()
    yield
    # Shutdown
    await db.shutdown()

app = FastAPI(
    title="Axiom.Q Quantum Telemetry Server",
    description="Server for quantum calibration experiment management and analysis",
    version="1.0.0",
    lifespan=lifespan,
)
```

Update `calibrate_qubit` — replace `log_calibration_run(...)` with:

```python
    try:
        await db.log_calibration_run(
            qubit_id=qubit_id,
            noise_parameters=inputs,
            raw_waveform_data=raw_counts,
            vlm_json_response=payload,
            outcome_fidelity=outcome_fidelity,
        )
    except Exception as e:
        log.warning("Calibration run log failed (non-fatal): %s", e)
```

Also add an error log path for the LiteLLM failure case:

```python
    except Exception as e:
        log.exception("LiteLLM call failed for %s: %s", qubit_id, e)
        # Try to log the failure
        try:
            await db.log_calibration_run(
                qubit_id=qubit_id,
                noise_parameters=inputs,
                raw_waveform_data=raw_counts,
                vlm_json_response={},
                outcome_fidelity=0.0,
                status="ERROR",
                error_detail=str(e),
            )
        except Exception:
            pass
        return {"status": "ERROR", "qubit_id": qubit_id, "reason": "litellm_error",
                "detail": str(e)}
```

Update `get_calibration_history` to be async:

```python
@app.get("/api/v1/history")
async def get_calibration_history(limit: int = 5):
    try:
        logs = await db.get_recent_history(limit=limit)
        return {"status": "SUCCESS", "history": logs}
    except Exception as e:
        log.warning("history lookup failed: %s", e)
        return {"status": "ERROR", "history": [], "message": str(e)}
```

- [ ] **Step 3: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/backend/db.py axiom-q/backend/main.py
git commit -m "feat: consolidate MongoDB into db.py with motor, lifespan-managed, auto-seed qubits, remove database.py"
```

---

## Task 5: Add Qubit API Endpoint

**Files:**
- Modify: `axiom-q/backend/main.py`

- [ ] **Step 1: Add `GET /api/v1/qubits` endpoint to `backend/main.py`**

Add after the health check endpoint:

```python
@app.get("/api/v1/qubits")
async def get_qubits():
    """Return all qubit configurations from MongoDB."""
    qubits = await db.get_all_qubits()
    if not qubits:
        return {"status": "ERROR", "reason": "mongodb_unavailable",
                "detail": "Could not fetch qubits from MongoDB. Ensure MongoDB is running."}
    return {"status": "SUCCESS", "qubits": qubits}
```

- [ ] **Step 2: Update the health check to include more info**

Replace the existing health check:

```python
@app.get("/")
async def health_check():
    mongo_ok = db.is_available()
    litellm_reachable = False
    litellm_url = os.getenv("LITELLM_URL", "http://127.0.0.1:4000/v1/chat/completions")
    try:
        import urllib.request
        base = litellm_url.replace("/v1/chat/completions", "").rstrip("/")
        req = urllib.request.Request(f"{base}/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            litellm_reachable = resp.status == 200
    except Exception:
        pass

    return {
        "status": "online",
        "service": "Axiom.Q Telemetry Server",
        "mongo_available": mongo_ok,
        "litellm_reachable": litellm_reachable,
        "litellm_url": litellm_url,
    }
```

- [ ] **Step 3: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/backend/main.py
git commit -m "feat: add GET /api/v1/qubits endpoint, enhanced health check with litellm reachability"
```

---

## Task 6: Frontend Store — Remove Static Data, Wire to API

**Files:**
- Modify: `axiom-q/src/store/useQuantumStore.js`

- [ ] **Step 1: Rewrite `useQuantumStore.js` with API-driven qubits and real error handling**

Replace the entire file:

```javascript
import { create } from "zustand";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/telemetry";

let ws = null;

const sendWebSocketMessage = (state, nextNoise = null, nextQubitIndex = null) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const noise = nextNoise || state.noise;
    const qubitId = `Q${nextQubitIndex !== null ? nextQubitIndex : state.selectedQubit}`;
    ws.send(
      JSON.stringify({
        qubit_id: qubitId,
        t1_relaxation: noise.t1_thermal,
        phase_damping: noise.phase_damping,
      })
    );
  }
};

const useQuantumStore = create((set, get) => ({
  /* ── Qubit State ── */
  qubit_state: {
    frequency: 0,
    amplitude: 0,
    t1_decay_value: 0,
  },
  qubits: [],       // Fetched from backend API
  qubits_loaded: false,
  qubits_error: null,

  selectedQubit: 0,

  /* ── Noise Channel Parameters ── */
  noise: {
    t1_thermal: 0.25,
    phase_damping: 0.15,
  },

  /* ── Telemetry Data ── */
  telemetry_data: {
    noisy: [],
    clean: [],
  },

  /* ── System Status ── */
  system_status: "UNCALIBRATED",

  /* ── Backend / Mongo readiness ── */
  backend_health: null,          // { mongo_available, litellm_reachable, ... }
  backend_health_error: null,

  /* ── AI Console Logs ── */
  ai_console_logs: [],

  /* ── JSON Payload Inspector ── */
  agent_payload: {
    status: "IDLE",
    correction_variables: {
      drift_compensation_mhz: 0.0,
      pi_pulse_amp_offset: 0.0,
    },
    confidence: null,
    model: "ising-calibration",
  },

  /* ── Actions ── */

  fetchHealth: async () => {
    try {
      const resp = await fetch(`${API_BASE}/`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      set({ backend_health: data, backend_health_error: null });
    } catch (e) {
      set({ backend_health: null, backend_health_error: e.message });
    }
  },

  fetchQubits: async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/qubits`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (data.status === "SUCCESS" && data.qubits?.length) {
        const qubits = data.qubits;
        const q = qubits[0];
        set({
          qubits,
          qubits_loaded: true,
          qubits_error: null,
          selectedQubit: 0,
          qubit_state: {
            frequency: q.frequency,
            amplitude: q.amplitude,
            t1_decay_value: q.t1_decay,
          },
        });
      } else {
        set({ qubits_error: data.detail || data.reason || "Unknown error fetching qubits", qubits_loaded: true });
      }
    } catch (e) {
      set({ qubits_error: `Failed to fetch qubits: ${e.message}`, qubits_loaded: true });
    }
  },

  initWebSocket: () => {
    if (ws) return;
    const addLog = (msg) =>
      set((s) => ({ ai_console_logs: [...s.ai_console_logs, { ts: Date.now(), msg }] }));

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        addLog("> WebSocket connected to backend.");
        sendWebSocketMessage(get());
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "telemetry_update") {
            set((state) => ({
              telemetry_data: {
                ...state.telemetry_data,
                noisy: data.probabilities,
              },
            }));
          } else if (data.event === "error" || data.error) {
            addLog(`> WebSocket error from backend: ${data.error || data.detail || JSON.stringify(data)}`);
          }
        } catch (e) {
          addLog(`> WebSocket parse error: ${e.message}`);
        }
      };
      ws.onerror = (e) => {
        addLog("> WebSocket connection error.");
      };
      ws.onclose = () => {
        addLog("> WebSocket disconnected. Reconnecting in 3s...");
        ws = null;
        setTimeout(connect, 3000);
      };
    };
    connect();
  },

  selectQubit: (index) =>
    set((state) => {
      const q = state.qubits[index];
      if (!q) return {};
      sendWebSocketMessage(state, null, index);
      return {
        selectedQubit: index,
        qubit_state: {
          frequency: q.frequency,
          amplitude: q.amplitude,
          t1_decay_value: q.t1_decay,
        },
      };
    }),

  setNoise: (key, value) =>
    set((state) => {
      const nextNoise = { ...state.noise, [key]: value };
      sendWebSocketMessage(state, nextNoise);
      return { noise: nextNoise };
    }),

  startCalibration: async () => {
    const state = get();
    if (state.system_status === "CALIBRATING") return;

    set({ system_status: "CALIBRATING" });
    const addLog = (msg) =>
      set((s) => ({
        ai_console_logs: [...s.ai_console_logs, { ts: Date.now(), msg }],
      }));

    const qubitId = `Q${state.selectedQubit}`;
    addLog(`> Initiating calibration for ${qubitId}...`);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await fetch(`${API_BASE}/api/v1/calibrate/${qubitId}`, {
        method: "POST",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      if (data.status === "SUCCESS") {
        const corrections = data.corrections || {};
        addLog(`> Calibration succeeded. Corrections received.`);
        set({
          system_status: "CALIBRATED",
          agent_payload: {
            status: "COMPLETE",
            correction_variables: {
              drift_compensation_mhz: corrections.drift_compensation_mhz ?? 0.0,
              pi_pulse_amp_offset: corrections.pi_pulse_amp_offset ?? 0.0,
            },
            confidence: data.confidence ?? null,
            model: "ising-calibration",
          },
        });

        // Smoothly reset noise sliders to zero
        const s = get();
        const startT1 = s.noise.t1_thermal;
        const startPd = s.noise.phase_damping;

        let step = 0;
        const steps = 30;
        const resetInterval = setInterval(() => {
          step++;
          const factor = 1 - (step / steps);

          set((state) => ({
            noise: {
              ...state.noise,
              t1_thermal: startT1 * factor,
              phase_damping: startPd * factor,
            }
          }));

          if (step >= steps) {
            clearInterval(resetInterval);
            set((state) => ({
              noise: { ...state.noise, t1_thermal: 0.0, phase_damping: 0.0 }
            }));
            sendWebSocketMessage(get(), { t1_thermal: 0.0, phase_damping: 0.0 });
          }
        }, 16);

        addLog("> Calibration complete. Corrections applied.");
        addLog(`> Δf = ${corrections.drift_compensation_mhz ?? 0} MHz | ΔA = ${corrections.pi_pulse_amp_offset ?? 0}`);
      } else {
        // Real error from backend
        const errMsg = data.detail || data.reason || data.message || JSON.stringify(data);
        addLog(`> Calibration error: ${errMsg}`);
        set({
          system_status: "UNCALIBRATED",
          agent_payload: {
            status: "ERROR",
            correction_variables: { drift_compensation_mhz: 0.0, pi_pulse_amp_offset: 0.0 },
            confidence: null,
            model: "ising-calibration",
          },
        });
      }
    } catch (e) {
      const msg = e.name === "AbortError" ? "Request timed out (120s)" : e.message;
      addLog(`> Calibration error: ${msg}`);
      set({
        system_status: "UNCALIBRATED",
        agent_payload: {
          status: "ERROR",
          correction_variables: { drift_compensation_mhz: 0.0, pi_pulse_amp_offset: 0.0 },
          confidence: null,
          model: "ising-calibration",
        },
      });
    }
  },

  resetCalibration: () =>
    set({
      system_status: "UNCALIBRATED",
      telemetry_data: { noisy: [], clean: [] },
      ai_console_logs: [
        { ts: Date.now(), msg: "> System reset. Awaiting calibration command..." },
      ],
      agent_payload: {
        status: "IDLE",
        correction_variables: {
          drift_compensation_mhz: 0.0,
          pi_pulse_amp_offset: 0.0,
        },
        confidence: null,
        model: "ising-calibration",
      },
    }),
}));

export default useQuantumStore;
```

Key changes:
- No `initialQubits` array — `qubits` starts empty, populated by `fetchQubits()`
- WS URL uses `VITE_WS_URL` env var instead of hardcoded `:8001`
- API base URL uses `VITE_API_BASE_URL`
- Removed all `setTimeout` fake log messages
- Error responses from backend are displayed verbatim in console
- `agent_payload.status` can be `"ERROR"` — a new state for the JSON inspector
- Added `fetchHealth()` for backend readiness
- Added `fetchQubits()` for initial data load

- [ ] **Step 2: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/src/store/useQuantumStore.js
git commit -m "feat: store uses API for qubits, env vars for URLs, real error surfacing, no mocks"
```

---

## Task 7: Frontend Components — Remove Static Data, Wire to Store

**Files:**
- Modify: `axiom-q/src/components/HardwarePanel/HardwarePanel.jsx`
- Modify: `axiom-q/src/App.jsx`

- [ ] **Step 1: Update `HardwarePanel.jsx` — remove local `QUBITS` array**

Replace `const QUBITS = Array.from({ length: 8 }, (_, i) => `Q${i}`);` with reading from the store:

```jsx
function QubitGrid() {
  const selectedQubit = useQuantumStore((s) => s.selectedQubit);
  const selectQubit = useQuantumStore((s) => s.selectQubit);
  const systemStatus = useQuantumStore((s) => s.system_status);
  const qubits = useQuantumStore((s) => s.qubits);
  const qubitsError = useQuantumStore((s) => s.qubits_error);

  if (qubitsError) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-400/70">
          <Cpu size={14} />
          <span>Qubit Register</span>
        </div>
        <p className="text-[10px] font-mono text-red-400">{qubitsError}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neon-cyan/70">
        <Cpu size={14} />
        <span>Qubit Register</span>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {qubits.map((q, i) => {
          const active = i === selectedQubit;
          return (
            <button
              key={q.label}
              onClick={() => selectQubit(i)}
              disabled={systemStatus === "CALIBRATING"}
              className={`
                relative flex flex-col items-center justify-center rounded-lg p-2
                border text-xs font-mono font-bold transition-all duration-200
                ${active
                  ? "bg-neon-cyan/10 border-neon-cyan/50 text-neon-cyan glow-cyan"
                  : "bg-surface-sunken/60 border-border-subtle text-slate-400 hover:border-slate-500 hover:text-slate-200"
                }
                disabled:opacity-40 disabled:cursor-not-allowed
              `}
            >
              <Atom size={16} className={active ? "text-neon-cyan" : "text-slate-500"} />
              <span className="mt-1">{q.label}</span>
              {active && (
                <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-neon-cyan animate-pulse" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

The `CalibrateButton` and `NoiseSlider` components stay as-is (they already read from store).

- [ ] **Step 2: Update `App.jsx` to fetch qubits and health on mount**

Replace the entire `App.jsx`:

```jsx
import { useEffect } from "react";
import Header from "./components/Header/Header";
import PanelCard from "./components/ui/PanelCard";
import useQuantumStore from "./store/useQuantumStore";

// Lazy-loaded panels for code splitting
import { lazy, Suspense } from "react";
import { SkeletonPanel } from "./components/ui/Skeleton";

const HardwarePanel = lazy(() => import("./components/HardwarePanel/HardwarePanel"));
const TelemetryPanel = lazy(() => import("./components/TelemetryPanel/TelemetryPanel"));
const AgentPanel = lazy(() => import("./components/AgentPanel/AgentPanel"));

export default function App() {
  const initWebSocket = useQuantumStore((s) => s.initWebSocket);
  const fetchQubits = useQuantumStore((s) => s.fetchQubits);
  const fetchHealth = useQuantumStore((s) => s.fetchHealth);

  useEffect(() => {
    fetchHealth();
    fetchQubits();
    initWebSocket();

    // Poll health every 30s
    const healthInterval = setInterval(fetchHealth, 30000);
    return () => clearInterval(healthInterval);
  }, [initWebSocket, fetchQubits, fetchHealth]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header />

      <main className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-5">
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-3 sm:gap-4 lg:gap-5 h-full">
          {/* ─── PANEL 1: Hardware Controls ─── */}
          <PanelCard className="min-h-0">
            <Suspense fallback={<SkeletonPanel />}>
              <HardwarePanel />
            </Suspense>
          </PanelCard>

          {/* ─── PANEL 2: Live Telemetry ─── */}
          <PanelCard className="min-h-0">
            <Suspense fallback={<SkeletonPanel />}>
              <TelemetryPanel />
            </Suspense>
          </PanelCard>

          {/* ─── PANEL 3: NVIDIA Ising Agent Console ─── */}
          <PanelCard className="min-h-0">
            <Suspense fallback={<SkeletonPanel />}>
              <AgentPanel />
            </Suspense>
          </PanelCard>
        </div>
      </main>

      {/* Footer status bar */}
      <footer className="flex items-center justify-between px-4 sm:px-6 py-1.5 border-t border-border-subtle bg-surface-card/40 text-[9px] font-mono text-slate-600 uppercase tracking-wider">
        <span>Axiom.Q v0.1.0-alpha</span>
        <span>NVIDIA Ising Agent + Quantum Telemetry</span>
        <span>JAMHacks 2026</span>
      </footer>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/src/App.jsx axiom-q/src/components/HardwarePanel/HardwarePanel.jsx
git commit -m "feat: App.jsx lazy loads panels, fetches qubits+health on mount; HardwarePanel reads qubits from store"
```

---

## Task 8: Skeleton Components + ErrorBoundary

**Files:**
- Create: `axiom-q/src/components/ui/Skeleton.jsx`
- Create: `axiom-q/src/components/ui/ErrorBoundary.jsx`

- [ ] **Step 1: Create `Skeleton.jsx`**

```jsx
/**
 * Skeleton / shimmer placeholders for lazy-loaded panels.
 */

export function SkeletonPanel() {
  return (
    <div className="animate-pulse space-y-4 p-2">
      {/* Header line */}
      <div className="h-4 w-32 rounded bg-slate-700/60" />
      {/* Grid of 8 small blocks */}
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-slate-700/40" />
        ))}
      </div>
      {/* Two slider tracks */}
      <div className="space-y-3">
        <div className="h-3 w-full rounded bg-slate-700/30" />
        <div className="h-3 w-full rounded bg-slate-700/30" />
      </div>
      {/* CTA button */}
      <div className="h-10 w-full rounded-xl bg-slate-700/40" />
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="animate-pulse flex flex-col gap-2 p-2">
      <div className="h-4 w-48 rounded bg-slate-700/60" />
      <div className="h-[220px] w-full rounded-xl bg-slate-700/20" />
      <div className="flex justify-between">
        <div className="h-3 w-12 rounded bg-slate-700/30" />
        <div className="h-3 w-24 rounded bg-slate-700/30" />
        <div className="h-3 w-12 rounded bg-slate-700/30" />
      </div>
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="animate-pulse flex items-center gap-3 py-2">
      <div className="h-3 w-3 rounded-full bg-slate-700/40" />
      <div className="h-3 flex-1 rounded bg-slate-700/30" />
    </div>
  );
}
```

- [ ] **Step 2: Create `ErrorBoundary.jsx`**

```jsx
import { Component } from "react";

/**
 * Catches render errors in the subtree and shows a styled error panel
 * instead of a blank white screen.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 max-w-md">
            <h3 className="text-sm font-bold text-red-400 uppercase tracking-widest mb-2">
              Runtime Error
            </h3>
            <pre className="text-xs font-mono text-red-300 whitespace-pre-wrap break-words">
              {this.state.error?.message || String(this.state.error)}
            </pre>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-4 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider
                         bg-surface-sunken border border-border-subtle text-slate-300
                         hover:border-slate-500 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 3: Wrap the app in ErrorBoundary in `main.jsx`**

Update `src/main.jsx`:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './components/ui/ErrorBoundary.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
```

- [ ] **Step 4: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/src/components/ui/Skeleton.jsx axiom-q/src/components/ui/ErrorBoundary.jsx axiom-q/src/main.jsx
git commit -m "feat: Skeleton shimmer components, ErrorBoundary, wrap app in error boundary"
```

---

## Task 9: StatusBar Component — Backend/Mongo/LiteLLM Readiness

**Files:**
- Create: `axiom-q/src/components/ui/StatusBar.jsx`
- Modify: `axiom-q/src/components/Header/Header.jsx`

- [ ] **Step 1: Create `StatusBar.jsx`**

```jsx
import useQuantumStore from "../../store/useQuantumStore";

function StatusDot({ ok, label }) {
  return (
    <span
      className={`flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider ${
        ok ? "text-neon-green" : "text-red-400"
      }`}
      title={label}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          ok ? "bg-neon-green" : "bg-red-400 animate-pulse"
        }`}
      />
      {label}
    </span>
  );
}

export default function StatusBar() {
  const health = useQuantumStore((s) => s.backend_health);
  const healthError = useQuantumStore((s) => s.backend_health_error);

  if (healthError) {
    return <StatusDot ok={false} label={`Backend: ${healthError}`} />;
  }

  if (!health) {
    return <StatusDot ok={false} label="Backend: checking..." />;
  }

  return (
    <div className="flex items-center gap-3">
      <StatusDot ok={health.mongo_available} label={health.mongo_available ? "MongoDB" : "MongoDB Down"} />
      <StatusDot ok={health.litellm_reachable} label={health.litellm_reachable ? "LiteLLM" : "LiteLLM Down"} />
    </div>
  );
}
```

- [ ] **Step 2: Add StatusBar to `Header.jsx`**

Update `Header.jsx` to import and render the StatusBar:

```jsx
import { Zap } from "lucide-react";
import useQuantumStore from "../../store/useQuantumStore";
import StatusBar from "../ui/StatusBar";

export default function Header() {
  const systemStatus = useQuantumStore((s) => s.system_status);

  const statusColor = {
    UNCALIBRATED: "bg-neon-amber",
    CALIBRATING: "bg-neon-purple animate-pulse",
    CALIBRATED: "bg-neon-green",
  };

  return (
    <header className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-border-subtle bg-surface-card/60 backdrop-blur-sm">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-neon-cyan/10 border border-neon-cyan/20 glow-cyan">
          <Zap size={16} className="text-neon-cyan" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-bold tracking-tight text-slate-100">
            Axiom<span className="text-neon-cyan">.Q</span>
          </span>
          <span className="text-[9px] text-slate-500 uppercase tracking-widest">
            Autonomous Quantum Control
          </span>
        </div>
      </div>

      {/* Status indicators */}
      <div className="flex items-center gap-4">
        <StatusBar />

        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${statusColor[systemStatus]}`} />
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">
            {systemStatus.replace("_", " ")}
          </span>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/src/components/ui/StatusBar.jsx axiom-q/src/components/Header/Header.jsx
git commit -m "feat: StatusBar component showing MongoDB and LiteLLM readiness in header"
```

---

## Task 10: TelemetryPanel — Skeleton for Chart While Data Loads

**Files:**
- Modify: `axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx`

- [ ] **Step 1: Add skeleton placeholder in TelemetryCard while awaiting first telemetry frame**

Import `SkeletonChart` at top:

```jsx
import { SkeletonChart } from "../ui/Skeleton";
```

In the `TelemetryCard` component, add a check before the chart renders:

```jsx
const hasTelemetry = telemetry.noisy && telemetry.noisy.length > 0;
```

Then in the return, replace the chart section with a conditional:

```jsx
<div className="relative w-full h-[220px] bg-surface-sunken/40 pt-4 pb-1 overflow-hidden">
  {systemStatus === "CALIBRATING" && (
    <div className="absolute inset-x-0 h-32 pointer-events-none z-50 animate-scan">
      <div className="w-full h-full bg-gradient-to-b from-transparent to-neon-cyan/20 border-b-2 border-neon-cyan glow-cyan" />
    </div>
  )}
  {hasTelemetry ? (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
        <XAxis dataKey="time" hide />
        <YAxis domain={[-1.2, 1.2]} tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '10px' }}
          itemStyle={{ color: '#e2e8f0' }}
        />
        <Line type="monotone" dataKey="Ideal" stroke="#a855f7" strokeWidth={1} dot={false} opacity={0.5} strokeDasharray="4 4" isAnimationActive={false} />
        <Line type="monotone" dataKey="Real" stroke="#00f0ff" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  ) : (
    <div className="flex flex-col items-center justify-center h-full">
      <SkeletonChart />
      <p className="text-[10px] font-mono text-slate-500 mt-1">Awaiting telemetry stream...</p>
    </div>
  )}
</div>
```

Note: the `chartData` useMemo still generates synthetic wave data when `hasRawData` is false (for the "ideal" reference line). This is intentional — the ideal Rabi line is a physics formula, not mock data. But the "Real" trace only appears when actual Qiskit simulation data arrives via WebSocket. When no real data exists, show the skeleton instead.

- [ ] **Step 2: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/src/components/TelemetryPanel/TelemetryPanel.jsx
git commit -m "feat: TelemetryPanel shows SkeletonChart while awaiting real telemetry data"
```

---

## Task 11: AgentPanel — Render Real Errors, No Fake Messages

**Files:**
- Modify: `axiom-q/src/components/AgentPanel/AgentPanel.jsx`

- [ ] **Step 1: Update `JsonInspector` to render ERROR status with red styling**

Add `const isError = payload.status === "ERROR";` and update the status badge to handle it:

```jsx
function JsonInspector() {
  const payload = useQuantumStore((s) => s.agent_payload);
  const isComplete = payload.status === "COMPLETE";
  const isError = payload.status === "ERROR";

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-card/80 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-200">
          <FileJson size={14} className={isError ? "text-red-400" : "text-neon-amber"} />
          Agent Payload Inspector
        </span>
        <span
          className={`text-[9px] font-mono font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border ${
            isError
              ? "bg-red-400/10 border-red-400/40 text-red-400"
              : isComplete
                ? "bg-neon-green/10 border-neon-green/40 text-neon-green"
                : "bg-surface-sunken border-border-subtle text-slate-500"
          }`}
        >
          {payload.status}
        </span>
      </div>

      {/* JSON Body */}
      <div className="p-3 font-mono text-[11px] leading-relaxed bg-surface-sunken/80 overflow-x-auto">
        {isError ? (
          <pre className="text-red-400 whitespace-pre-wrap">{JSON.stringify(payload, null, 2)}</pre>
        ) : (
          <>
            <pre className="text-slate-400">
              <span className="text-slate-600">{"{"}</span>
              {"\n"}
              <span className="ml-3 text-slate-500">"model"</span>
              <span className="text-slate-600">: </span>
              <span className="text-neon-amber">"{payload.model}"</span>
              <span className="text-slate-600">,</span>
              {"\n"}
              <span className="ml-3 text-slate-500">"confidence"</span>
              <span className="text-slate-600">: </span>
              <span className={isComplete ? "text-neon-green" : "text-slate-600"}>
                {payload.confidence ?? "null"}
              </span>
              <span className="text-slate-600">,</span>
              {"\n"}
              <span className="ml-3 text-slate-500">"correction_variables"</span>
              <span className="text-slate-600">: {"{"}</span>
              {"\n"}
              {Object.entries(payload.correction_variables).map(([key, val], i, arr) => (
                <span key={key}>
                  <span className="ml-6 text-neon-cyan">{key}</span>
                  <span className="text-slate-600">: </span>
                  <span className={isComplete ? "text-neon-green" : "text-slate-600"}>
                    {val}
                  </span>
                  {i < arr.length - 1 && <span className="text-slate-600">,</span>}
                  {"\n"}
                </span>
              ))}
              <span className="ml-3 text-slate-600">{"}"}</span>
              {"\n"}
              <span className="text-slate-600">{"}"}</span>
            </pre>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/src/components/AgentPanel/AgentPanel.jsx
git commit -m "feat: AgentPanel shows ERROR status in red, displays real error payloads from backend"
```

---

## Task 12: Update Agent payload key mapping

**Files:**
- Modify: `axiom-q/src/store/useQuantumStore.js`

- [ ] **Step 1: Fix correction key name mismatch**

The backend returns `corrections.pi_pulse_amp_offset` and `corrections.drift_compensation_mhz`, but the payload inspector uses the same keys. Verify the mapping in `startCalibration` is consistent.

In `startCalibration` success handler, the store already maps:
```javascript
correction_variables: {
  drift_compensation_mhz: corrections.drift_compensation_mhz ?? 0.0,
  pi_pulse_amp_offset: corrections.pi_pulse_amp_offset ?? 0.0,
},
```

But the backend `calibrate_qubit` returns:
```python
corrections = {
    "pi_pulse_amp_offset": vlm_data.get("pi_pulse_amp_mod", 0.0),
    "drift_compensation_mhz": vlm_data.get("drift_corrected_mhz", 0.0),
}
```

The NVIDIA model returns `pi_pulse_amp_mod` and `drift_corrected_mhz`, which the backend remaps to `pi_pulse_amp_offset` and `drift_compensation_mhz`. This is already correct on the backend side — the frontend reads the remapped keys. No change needed, just verify.

- [ ] **Step 2: Commit if any fixes were needed (otherwise skip)**

---

## Task 13: MongoDB Compass & VS Code Extension Setup Guide

**Files:**
- Modify: `axiom-q/README.md`

- [ ] **Step 1: Update `README.md` with full setup instructions**

Add MongoDB Compass and VS Code extension sections:

```markdown
## MongoDB Setup

### Option A: Local mongod (recommended)

1. Install MongoDB Community Server: https://www.mongodb.com/try/download/community
2. Start the service:
   ```bash
   # Windows (runs as service after install — or manually):
   net start MongoDB
   # Or start manually:
   mongod --dbpath C:\data\db
   ```
3. Verify it's running:
   ```bash
   mongosh "mongodb://localhost:27017"
   ```

### Option B: MongoDB Compass (GUI)

1. Download: https://www.mongodb.com/try/download/compass
2. Open Compass → paste connection string: `mongodb://localhost:27017`
3. Create database `axiom_q` with collections:
   - `qubits` (auto-seeded on first backend startup)
   - `telemetry` (populated by WebSocket sessions)
   - `calibration_history` (populated by calibration runs)

### Option C: VS Code MongoDB Extension

1. Install "MongoDB for VS Code" extension from the marketplace
2. Open the MongoDB panel in the sidebar (leaf icon)
3. Click "Connect with Connection String"
4. Paste: `mongodb://localhost:27017`
5. Expand `axiom_q` database to browse collections

### Seeding

The backend **auto-seeds** the 8-qubit register on first startup if the `qubits` collection is empty. No manual seeding required.
```

Keep the existing LiteLLM and backend setup sections, removing references to `vlm_proxy.py`.

- [ ] **Step 2: Commit**

```bash
cd d:/JAMHacks
git add axiom-q/README.md
git commit -m "docs: update README with MongoDB Compass/VS Code extension setup, remove vlm_proxy references"
```

---

## Task 14: Verify Build + Integration Test

**Files:** None (verification only)

- [ ] **Step 1: Install python-dotenv in backend**

```bash
cd d:/JAMHacks/axiom-q/backend
pip install python-dotenv
```

- [ ] **Step 2: Build the frontend and verify code splitting**

```bash
cd d:/JAMHacks/axiom-q
npm run build
```

Check the `dist/assets/` directory for multiple JS chunks — should see separate chunks for `three`, `vendor`, and `app`.

- [ ] **Step 3: Start MongoDB locally**

```bash
# If mongod is installed as a Windows service:
net start MongoDB
# Otherwise start manually:
mongod --dbpath C:\data\db
```

- [ ] **Step 4: Start the backend**

```bash
cd d:/JAMHacks/axiom-q
python -m backend.main
```

If MongoDB is running: should see "MongoDB connected" + "Seeded 8 qubits" logs.
If MongoDB is NOT running: should see a clear `ServerSelectionTimeoutError` and the server still starts (lifespan logs a warning but doesn't crash — the health endpoint will report `mongo_available: false`).

Actually — per the design decision, MongoDB should be **required**. So update the lifespan in `db.py` to raise if Mongo is truly unreachable:

```python
async def startup():
    global _client, _db, telemetry_col, qubits_col, history_col
    _client = AsyncIOMotorClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
    )
    try:
        await _client.admin.command("ping")
    except Exception as e:
        log.error("MongoDB is NOT reachable at %s: %s", MONGODB_URI, e)
        log.error("Start MongoDB before running the server.")
        # Don't crash — allow server to start but flag as unavailable
        # (This lets the frontend show the "MongoDB Down" status dot)
```

- [ ] **Step 5: Verify the frontend with `npm run dev`**

Open browser to `http://localhost:5173`. Expected:
- Skeleton panels flash briefly while lazy-loaded chunks resolve
- Header shows "MongoDB" and "LiteLLM" status dots (red if not running)
- Qubit grid shows Q0-Q7 (fetched from API)
- Telemetry chart shows "Awaiting telemetry stream..." until you move a noise slider
- Clicking "Run Autonomous Calibration" with LiteLLM down shows the actual error in the Agent console

- [ ] **Step 6: Final commit with any fixes**

```bash
cd d:/JAMHacks
git add -A
git commit -m "chore: verify build, code splitting, integration test"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Create .env files (backend + frontend) | Tasks 1, 2 |
| Move all secrets to env | Task 1 (LITELLM_API_KEY, MONGODB_URI, etc.) |
| Delete vlm_proxy.py | Task 3 |
| Delete database.py, consolidate | Task 4 |
| Delete _make_demo_telemetry | Task 3 |
| Delete DEFAULT_CORRECTIONS | Task 3 |
| Delete hardcoded outcome_fidelity | Task 3 |
| Delete setTimeout fake logs | Task 6 |
| Delete hardcoded qubit arrays | Task 6 |
| Fix WS port (:8001 → :8000 via env) | Task 6 |
| Qubits API + Mongo-backed | Tasks 4, 5 |
| Real error propagation | Tasks 3, 5, 6 |
| Fallback methods + show error | Tasks 3, 6, 8, 11 |
| Lazy loading + Suspense | Task 7 |
| Skeleton components | Task 8 |
| StatusBar (Mongo/LiteLLM dots) | Task 9 |
| TelemetryChart skeleton | Task 10 |
| AgentPanel error state | Task 11 |
| MongoDB Compass / VS Code docs | Task 13 |
| Build verification | Task 14 |

### Placeholder Scan
No "TBD", "TODO", "implement later", or "similar to Task N" patterns found. Every step contains concrete code or commands.

### Type Consistency
- `qubits` in store → `[{label, frequency, amplitude, t1_decay}]` (matches `db._default_qubits()` output)
- `corrections.drift_compensation_mhz` / `corrections.pi_pulse_amp_offset` — backend `calibrate_qubit` returns these keys, frontend reads them
- `agent_payload.status` — values: `"IDLE"`, `"COMPLETE"`, `"ERROR"` — all handled in JsonInspector

---

Plan complete and saved to `docs/superpowers/plans/2026-06-13-axiom-q-hardening.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
