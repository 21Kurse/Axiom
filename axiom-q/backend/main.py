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
import io
import base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


# ── Prosthetic live-mode state ────────────────────────────────────────
PROSTHETIC_THRESHOLD = float(os.getenv("PROSTHETIC_THRESHOLD", "0.30"))


class ProstheticState:
    """Single-writer state used by /ws/prosthetic to drive the live demo."""

    def __init__(self) -> None:
        self.pot_value: float = 0.0
        self.armed: bool = True
        self.cycle_running: bool = False
        self.last_status: str = "READY"
        self.last_ts: float = 0.0

    def note_pot(self, value: float, ts: float) -> bool:
        """Update the pot value. Returns True if a new cycle was armed."""
        self.pot_value = max(0.0, min(1.0, float(value)))
        self.last_ts = float(ts)
        if (
            self.armed
            and not self.cycle_running
            and self.pot_value >= PROSTHETIC_THRESHOLD
        ):
            self.armed = False
            self.cycle_running = True
            return True
        return False

    def reset(self) -> None:
        self.pot_value = 0.0
        self.armed = True
        self.last_status = "READY"


prosthetic_state = ProstheticState()


async def _prosthetic_broadcast(payload: dict) -> None:
    """Wrap the connection-manager broadcast with a service tag."""
    await manager.broadcast({"service": "prosthetic", **payload})


async def _run_prosthetic_cycle(pot_value: float) -> None:
    """Background task — full pipeline + per-frame cell-state broadcasts."""
    try:
        from backend.prosthetics import main as prosthetics_main
        await prosthetics_main.run_one_cycle(
            pot_value=pot_value,
            seed=None,
            broadcast=_prosthetic_broadcast,
            save_gif=False,
            frame_interval_s=0.05,
        )
    except Exception as exc:  # pragma: no cover - never want to crash the loop
        log.exception("Prosthetic cycle failed: %s", exc)
        try:
            await _prosthetic_broadcast({
                "type": "status",
                "phase": "ERROR",
                "error": str(exc),
            })
        except Exception:
            pass
    finally:
        prosthetic_state.cycle_running = False
        prosthetic_state.armed = True
        prosthetic_state.pot_value = 0.0
        try:
            await _prosthetic_broadcast({
                "type": "status",
                "phase": "READY",
                "pot_value": 0.0,
            })
        except Exception:
            pass


@app.websocket("/ws/prosthetic")
async def prosthetic_websocket(websocket: WebSocket):
    """
    Bidirectional WebSocket for the prosthetic live demo.

    Inbound (from React):
        {"type": "pot", "value": 0.45, "ts": 1700000000.0}
        {"type": "reset"}      ← judge button to re-arm

    Outbound (to React):
        {"service": "prosthetic", "type": "status",     ...}
        {"service": "prosthetic", "type": "cell_state", ...}
        {"service": "prosthetic", "type": "heatmap",    ...}
        {"service": "prosthetic", "type": "diagnosis",  ...}
        {"service": "prosthetic", "type": "pot",        ...}

    When the pot crosses ``PROSTHETIC_THRESHOLD`` (rising edge, while armed),
    a full telemetry → heatmap → VLM → healing cycle is fired in the background,
    broadcasting each frame's cell state so the Three.js mesh can tween in lockstep.
    """
    await manager.connect(websocket)
    try:
        # Initial sync — let the client know what state the server thinks it's in.
        await websocket.send_json({
            "service": "prosthetic",
            "type": "status",
            "phase": prosthetic_state.last_status,
            "pot_value": prosthetic_state.pot_value,
            "threshold": PROSTHETIC_THRESHOLD,
        })

        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "service": "prosthetic",
                    "type": "error",
                    "error": "Invalid JSON payload",
                })
                continue

            kind = payload.get("type")

            if kind == "pot":
                pot = float(payload.get("value", 0.0))
                ts = float(payload.get("ts", 0.0))
                fired = prosthetic_state.note_pot(pot, ts)
                await _prosthetic_broadcast({"type": "pot", "value": pot, "ts": ts})
                if fired:
                    log.info(
                        "Prosthetic live cycle fired at pot=%.3f (threshold=%.2f)",
                        pot, PROSTHETIC_THRESHOLD,
                    )
                    asyncio.create_task(_run_prosthetic_cycle(pot))

            elif kind == "reset":
                prosthetic_state.reset()
                await _prosthetic_broadcast({
                    "type": "status",
                    "phase": "READY",
                    "pot_value": 0.0,
                })

            else:
                await websocket.send_json({
                    "service": "prosthetic",
                    "type": "error",
                    "error": f"Unknown message type: {kind!r}",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:  # pragma: no cover - never crash the loop
        log.exception("Prosthetic WS error: %s", exc)
        manager.disconnect(websocket)


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
            hardware_drift = float(payload.get("hardware_drift", 0.0))
            pulse_amp_mod = float(payload.get("pulse_amp_mod", 1.0))

            try:
                sim = await run_rabi_simulation(
                    t1_relaxation, phase_damping,
                    drift_mhz=hardware_drift,
                    pulse_amp_mod=pulse_amp_mod,
                )
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

            inputs = {
                "t1_relaxation": t1_relaxation,
                "phase_damping": phase_damping,
                "hardware_drift": hardware_drift,
                "pulse_amp_mod": pulse_amp_mod,
            }

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


@app.get("/api/v1/telemetry/{qubit_id}/plot")
async def get_telemetry_plot(qubit_id: str):
    """
    Dedicated telemetry route that exports the noisy Matplotlib curve 
    as a base64 string payload for the VLM to analyze.
    """
    doc = telemetry_store.get_latest_telemetry(qubit_id)
    if not doc:
        return {"error": "No telemetry available for this qubit."}
    
    raw_counts = doc.get("raw_counts") or []
    probs = doc.get("probabilities") or _probs_from_raw_counts(raw_counts)
    
    if not probs:
        return {"error": "No probability data available."}
        
    plt.figure(figsize=(8, 4))
    plt.plot(probs, label=f"Rabi Oscillation ({qubit_id})", color="cyan")
    plt.title(f"Noisy Telemetry Data: {qubit_id}")
    plt.xlabel("Drive Duration")
    plt.ylabel("Probability P(|1>)")
    plt.grid(True, linestyle="--", alpha=0.5)
    
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return {"status": "SUCCESS", "plot_base64": b64}



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

    # Generate the base64 plot to send to the VLM Proxy
    image_base64 = None
    if probs:
        import io
        import base64
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8, 4))
        plt.plot(probs, label=f"Rabi Oscillation ({qubit_id})", color="cyan")
        plt.title(f"Noisy Telemetry Data: {qubit_id}")
        plt.xlabel("Drive Duration")
        plt.ylabel("Probability P(|1>)")
        plt.grid(True, linestyle="--", alpha=0.5)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        image_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Call LiteLLM — propagate real errors if it fails
    try:
        vlm_data = await call_nvidia_ising_model(qubit_id, probs, inputs, image_base64=image_base64)
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

    # nvidia_client now normalizes keys to canonical names
    corrections = {
        "pi_pulse_amp_offset": vlm_data.get("pi_pulse_amp_mod", 0.0),
        "drift_compensation_mhz": vlm_data.get("drift_compensation_mhz", 0.0),
    }

    t1_relax = float(inputs.get("t1_relaxation", 0.0))
    pd = float(inputs.get("phase_damping", 0.0))
    raw_drift = float(inputs.get("hardware_drift", 0.0))
    amp_mod = float(inputs.get("pulse_amp_mod", 1.0))

    # The ising-calibration model emits a near-constant confidence regardless of
    # input, so derive a data-driven confidence from the signal physics instead:
    # how much Rabi oscillation visibility survives the current T1/dephasing
    # environment (clean signal → ~1.0, fully decohered → ~0.0).
    from backend.quantum_engine import compute_analytical_rabi, signal_confidence
    confidence = signal_confidence(t1_relax, pd, drift_mhz=raw_drift, pulse_amp_mod=amp_mod)

    # Compute outcome fidelity by comparing corrected vs uncorrected Rabi curves
    # Fidelity = how much the correction restores the oscillation dynamic range
    corrected_drift = raw_drift - corrections["drift_compensation_mhz"]
    corrected_amp = amp_mod + corrections["pi_pulse_amp_offset"]

    try:
        uncorrected = compute_analytical_rabi(t1_relax, pd, drift_mhz=raw_drift, pulse_amp_mod=amp_mod)
        corrected = compute_analytical_rabi(t1_relax, pd, drift_mhz=corrected_drift, pulse_amp_mod=corrected_amp)
        uc_range = max(uncorrected) - min(uncorrected) if uncorrected else 0.0
        c_range = max(corrected) - min(corrected) if corrected else 0.0
        # Fidelity: ratio of corrected dynamic range to uncorrected, capped at 1.0
        outcome_fidelity = min(1.0, c_range / uc_range) if uc_range > 0.01 else 0.0
    except Exception:
        # Fallback to confidence if analytical comparison fails
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

    # Calibration complete. The frontend renders the corrected waveform using
    # the active environmental noise parameters; no zero-noise override.
    return payload


from fastapi.responses import FileResponse

@app.get("/api/v1/prosthetics/heatmap")
async def get_prosthetics_heatmap():
    """Serve the generated heatmap image from the prosthetics package."""
    path = os.path.join(os.path.dirname(__file__), "prosthetics", "heatmap_noisy.png")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    return {
        "status": "ERROR",
        "reason": "not_found",
        "detail": "Heatmap image not yet generated. Drag the slider to run a live calibration cycle first."
    }


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
