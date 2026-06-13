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
    """Connect and verify MongoDB. Logs a clear error if unavailable."""
    global _client, _db, telemetry_col, qubits_col, history_col
    _client = AsyncIOMotorClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
    )
    try:
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
    except Exception as e:
        log.error("MongoDB is NOT reachable at %s: %s", MONGODB_URI, e)
        log.error("Start MongoDB before running the server. The app will start but report mongo_available=false.")


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
