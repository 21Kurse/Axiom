import os
from motor.motor_asyncio import AsyncIOMotorClient

# Default to local MongoDB instance — but it's optional.
# We expose `is_available()` so the rest of the app can fail fast.
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Tight timeouts so a missing Mongo never blocks the calibrate endpoint.
_client = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=1500,   # fail fast on connect
    connectTimeoutMS=1500,
    socketTimeoutMS=2000,
)

db = _client.axiom_q
telemetry_collection = db.calibration_history


def is_available() -> bool:
    """Synchronous, non-blocking probe. Returns True if Mongo is reachable NOW."""
    try:
        # `nodes` is a frozenset of (address, server_type) tuples — populated when pymongo
        # has talked to the server. If empty, no server has been contacted yet.
        return bool(_client.nodes)
    except Exception:
        return False


async def insert_telemetry(record: dict) -> None:
    """Insert without ever blocking responses on Mongo failures."""
    if not is_available():
        return
    try:
        await telemetry_collection.insert_one(record)
    except Exception as e:
        print(f"[mongo] insert skipped: {e}")


async def get_latest_uncalibrated_telemetry(qubit_id: str):
    """Return the latest UNCALIBRATED doc, or None if Mongo unavailable."""
    if not is_available():
        return None
    try:
        doc = await telemetry_collection.find_one(
            {"qubit_id": qubit_id, "status": "UNCALIBRATED"},
            sort=[("timestamp", -1)],
        )
        return doc
    except Exception as e:
        print(f"[mongo] query skipped: {e}")
        return None


async def update_telemetry_status(doc_id, status: str, corrections: dict = None) -> None:
    """Update without ever blocking responses on Mongo failures."""
    if not is_available():
        return
    try:
        update_doc = {"status": status}
        if corrections:
            update_doc["corrections"] = corrections
        await telemetry_collection.update_one({"_id": doc_id}, {"$set": update_doc})
    except Exception as e:
        print(f"[mongo] update skipped: {e}")
