"""
In-memory telemetry store
Captures the latest raw_counts + probabilities for each qubit so that calibration
requests can be answered without depending on MongoDB.
"""
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

_LOCK = threading.Lock()
# qubit_id -> {"raw_counts": [...], "probabilities": [...], "inputs": {...}, "timestamp": str}
_LATEST: Dict[str, Dict[str, Any]] = {}
# short history per qubit for the calibration log
_HISTORY: Dict[str, deque] = {}
_HISTORY_MAX = 20


def record_telemetry(qubit_id: str, raw_counts: list, probabilities: list, inputs: dict) -> None:
    """Store the most recent telemetry for a qubit."""
    with _LOCK:
        record = {
            "qubit_id": qubit_id,
            "raw_counts": raw_counts,
            "probabilities": probabilities,
            "inputs": inputs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "UNCALIBRATED",
        }
        _LATEST[qubit_id] = record
        history = _HISTORY.setdefault(qubit_id, deque(maxlen=_HISTORY_MAX))
        history.append(record)


def get_latest_telemetry(qubit_id: str) -> Optional[Dict[str, Any]]:
    """Return the latest telemetry record for a qubit (if any)."""
    with _LOCK:
        record = _LATEST.get(qubit_id)
        return dict(record) if record else None


def mark_calibrated(qubit_id: str, corrections: dict) -> None:
    """Flip the latest record's status to CALIBRATED and attach corrections."""
    with _LOCK:
        record = _LATEST.get(qubit_id)
        if record:
            record["status"] = "CALIBRATED"
            record["corrections"] = corrections


def get_history(qubit_id: str) -> list:
    with _LOCK:
        history = _HISTORY.get(qubit_id)
        return list(history) if history else []
