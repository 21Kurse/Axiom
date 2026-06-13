"""
Axiom.Q Quantum Telemetry Server
FastAPI app for quantum calibration experiment management.
Handles WebSocket telemetry streaming and VLM-based calibration analysis.
"""

from dotenv import load_dotenv
load_dotenv()

import json
import asyncio
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.quantum_engine import run_rabi_simulation
from backend import db
from backend import telemetry_store
from backend.nvidia_client import call_nvidia_ising_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("axiom-q")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — connect to MongoDB
    await db.startup()
    yield
    # Shutdown — close MongoDB client
    await db.shutdown()


app = FastAPI(
    title="Axiom.Q Quantum Telemetry Server",
    description="Server for quantum calibration experiment management and analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — configurable via FRONTEND_ORIGINS env var
_origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for c in self.active_connections:
            try:
                await c.send_json(message)
            except Exception:
                disconnected.append(c)
        for c in disconnected:
            self.disconnect(c)


manager = ConnectionManager()


@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    """
    Bidirectional WebSocket for live telemetry.
    Each inbound packet updates the in-memory record + (optionally) Mongo for that qubit.
    """
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON payload"})
                continue

            qubit_id = payload.get("qubit_id", "Q0")
            t1_relaxation = float(payload.get("t1_relaxation", 0.0))
            phase_damping = float(payload.get("phase_damping", 0.0))

            try:
                sim = await run_rabi_simulation(t1_relaxation, phase_damping)
                probabilities = sim["probabilities"]
                raw_counts = sim["raw_counts"]
            except Exception as e:
                log.exception("Simulation error: %s", e)
                await websocket.send_json({"event": "error", "error": f"Simulation error: {e}"})
                continue

            await websocket.send_json({
                "event": "telemetry_update",
                "qubit_id": qubit_id,
                "probabilities": probabilities,
            })

            inputs = {"t1_relaxation": t1_relaxation, "phase_damping": phase_damping}

            # 1) Always record in memory — never blocks.
            telemetry_store.record_telemetry(qubit_id, raw_counts, probabilities, inputs)
            # 2) Optionally persist, never blocks the WS loop on Mongo failures.
            asyncio.create_task(db.insert_telemetry({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "qubit_id": qubit_id,
                "inputs": inputs,
                "raw_counts": raw_counts,
                "status": "UNCALIBRATED",
            }))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _probs_from_raw_counts(raw_counts: list) -> list:
    out = []
    for c in raw_counts:
        total = sum(c.values()) if c else 0
        out.append(c.get("1", 0) / total if total > 0 else 0.0)
    return out


@app.post("/api/v1/calibrate/{qubit_id}")
async def calibrate_qubit(qubit_id: str):
    """
    Use the most recently-ingested telemetry for this qubit (in-memory)
    and ask the LiteLLM-routed NVIDIA Ising model for corrections.
    Returns real corrections from LiteLLM or an error response if unavailable.
    """
    # 1) Prefer in-memory telemetry populated by /ws/telemetry.
    doc = telemetry_store.get_latest_telemetry(qubit_id)

    # 2) Fall back to Mongo if available (best effort, short-timeout).
    if not doc:
        doc = await db.get_latest_uncalibrated_telemetry(qubit_id)

    # 3) No telemetry available — return error (no fake data).
    if not doc:
        return {"status": "ERROR", "qubit_id": qubit_id, "reason": "no_telemetry_for_qubit",
                "detail": f"No telemetry data available for qubit {qubit_id}. Send noise parameters via the telemetry WebSocket first."}

    inputs = doc.get("inputs") or {}
    raw_counts = doc.get("raw_counts") or []
    probs = doc.get("probabilities") or _probs_from_raw_counts(raw_counts)

    log.info("Calibrating %s with %d probability samples.", qubit_id, len(probs))

    # Call LiteLLM — propagate real errors if it fails
    try:
        vlm_data = await call_nvidia_ising_model(qubit_id, probs, inputs)
    except Exception as e:
        log.exception("LiteLLM call failed for %s: %s", qubit_id, e)
        # Log the failure to history
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

    log.info("LiteLLM returned: %s", vlm_data)

    corrections = {
        "pi_pulse_amp_offset": vlm_data.get("pi_pulse_amp_mod", 0.0),
        "drift_compensation_mhz": vlm_data.get("drift_corrected_mhz", 0.0),
    }
    confidence = vlm_data.get("confidence", 0.0)

    # Compute outcome fidelity from the model's confidence
    outcome_fidelity = float(confidence) if confidence else 0.0

    payload = {
        "status": "SUCCESS",
        "qubit_id": qubit_id,
        "corrections": corrections,
        "confidence": confidence,
        "outcome_fidelity": outcome_fidelity,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "source": "litellm",
    }

    # Update in-memory record + fire-and-forget Mongo writes (already non-blocking).
    telemetry_store.mark_calibrated(qubit_id, payload)
    doc_id = doc.get("_id")
    if doc_id and db.is_available():
        asyncio.create_task(db.update_telemetry_status(doc_id, "CALIBRATED", payload))

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

    # Broadcast a fresh "clean" waveform (no noise) to all connected clients.
    try:
        sim = await run_rabi_simulation(0.0, 0.0)
        await manager.broadcast({
            "event": "telemetry_update",
            "qubit_id": qubit_id,
            "probabilities": sim["probabilities"],
        })
    except Exception as e:
        log.warning("Broadcast failed (non-fatal): %s", e)

    return payload


@app.get("/api/v1/qubits")
async def get_qubits():
    """Return all qubit configurations from MongoDB."""
    qubits = await db.get_all_qubits()
    if not qubits and not db.is_available():
        return {"status": "ERROR", "reason": "mongodb_unavailable",
                "detail": "Could not fetch qubits from MongoDB. Ensure MongoDB is running."}
    if not qubits:
        return {"status": "SUCCESS", "qubits": []}
    return {"status": "SUCCESS", "qubits": qubits}


@app.get("/api/v1/telemetry/{qubit_id}")
async def get_latest_telemetry(qubit_id: str):
    """Return whatever telemetry is currently held in memory for a qubit."""
    record = telemetry_store.get_latest_telemetry(qubit_id)
    if not record:
        return {"status": "EMPTY", "qubit_id": qubit_id}
    return {"status": "OK", "telemetry": record}


@app.get("/api/v1/history")
async def get_calibration_history(limit: int = 5):
    try:
        logs = await db.get_recent_history(limit=limit)
        return {"status": "SUCCESS", "history": logs}
    except Exception as e:
        log.warning("history lookup failed: %s", e)
        return {"status": "ERROR", "history": [], "message": str(e)}


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


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
