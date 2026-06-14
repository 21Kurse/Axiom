"""
Prosthetics Audit Ledger
=========================
Records every telemetry → drift → diagnosis → healing cycle into MongoDB
for full audit traceability. Also provides a comfort history timeline
for the patient dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
import pymongo

from backend.db import MONGODB_URI, MONGODB_DB_NAME

log = logging.getLogger("axiom-q.prosthetics.ledger")


def get_sync_db() -> pymongo.database.Database:
    """Get a synchronous pymongo Database instance."""
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
    return client[MONGODB_DB_NAME]


def record(
    target: Any,
    drifted: Any,
    drift_cells: list[tuple[int, int]],
    diagnosis: dict,
    healed: Any,
) -> dict:
    """
    Log a full pipeline cycle to MongoDB.

    Parameters
    ----------
    target : np.ndarray
        Clean pressure grid.
    drifted : np.ndarray
        Drifted pressure grid.
    drift_cells : list[tuple[int, int]]
        Cells affected by drift.
    diagnosis : dict
        VLM analysis result containing JSON corrections.
    healed : np.ndarray
        Post-healing pressure grid.

    Returns
    -------
    dict
        Ledger entry that was persisted.
    """
    # Convert numpy types to native Python types for MongoDB serialization
    drift_cells_native = [
        [int(r), int(c)] for r, c in drift_cells
    ]
    
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "drift_cell_count": len(drift_cells),
        "drift_cells": drift_cells_native,
        "drifted_grid": drifted.tolist() if hasattr(drifted, "tolist") else drifted,
        "diagnosis": diagnosis,
        "healed_grid": healed.tolist() if hasattr(healed, "tolist") else healed,
    }
    
    try:
        db = get_sync_db()
        db.calibration_history.insert_one(entry.copy())
        log.info("Ledger — persisted cycle to MongoDB (calibration_history)")
    except Exception as e:
        log.warning("Ledger — could not connect to MongoDB: %s", e)
        
    return entry


def print_timeline() -> None:
    """Fetch and display the last 5 entries as a Comfort History Timeline."""
    try:
        db = get_sync_db()
        history = list(db.calibration_history.find().sort("timestamp", -1).limit(5))
        
        if not history:
            print("\n🕒 Comfort History Timeline: No entries yet.")
            return
            
        print("\n🕒 Comfort History Timeline (Last 5 events):")
        print("--------------------------------------------------")
        for i, entry in enumerate(history, 1):
            ts = entry.get("timestamp", "Unknown Time")
            
            # Format timestamp nicely if possible
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, AttributeError):
                ts_str = ts
                
            drift_count = entry.get("drift_cell_count", 0)
            zone = entry.get("diagnosis", {}).get("drift_zone", "Unknown")
            print(f" {i}. [{ts_str}] Drifted cells: {drift_count} | Zone: {zone}")
        print("--------------------------------------------------\n")
    except Exception as e:
        log.warning("Could not fetch timeline from MongoDB: %s", e)
