"""
Prosthetics Arduino Serial Bridge
==================================
Reads two potentiometer values from an Arduino Uno over Serial USB and
feeds them into the existing prosthetics pipeline:

  - **Pot 1** (A0): "Limb-Shift" knob → feeds ``pot_value`` into the
    existing ``/ws/prosthetic`` prosthetic cycle.  When the pot crosses
    the server-side threshold (default 0.30), a full telemetry → heatmap
    → VLM → healing cycle fires automatically.
  - **Pot 2** (A1): "Comfort-Target" knob → dynamically adjusts the
    target pressure range that ``telemetry.generate_target_array()``
    uses instead of the hardcoded ``[8, 12]`` kPa defaults.

Wire protocol
-------------
The Arduino sends CSV lines at ~30 Hz, 9600 baud::

    pot1_raw,pot2_raw\\n

where each value is an integer in ``[0, 1023]`` (10-bit ADC).

Usage
-----
Enable by setting ``ENABLE_ARDUINO=true`` in ``backend/.env``.
The serial port defaults to ``ARDUINO_PORT=COM3`` (Windows) or
``/dev/ttyACM0`` (Linux).  The bridge starts as a background task
in the FastAPI lifespan and auto-reconnects on disconnect.

If the Arduino is not connected or the env var is off, all calls
to :func:`get_target_pressure_range` fall back to the hard-coded
defaults — the soft-UI-only path is unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

log = logging.getLogger("axiom-q.prosthetics.arduino_io")

# ── Configuration (env-driven) ──────────────────────────────────────────

ENABLED = os.getenv("ENABLE_ARDUINO", "false").lower() in ("true", "1", "yes")
PORT = os.getenv("ARDUINO_PORT", "COM3")
BAUD = int(os.getenv("ARDUINO_BAUD", "9600"))
RECONNECT_DELAY = float(os.getenv("ARDUINO_RECONNECT_DELAY", "3.0"))
READ_TIMEOUT = float(os.getenv("ARDUINO_READ_TIMEOUT", "2.0"))

# ── Pressure-range mapping for Pot 2 ───────────────────────────────────
# Pot 2 @ 0% → very loose socket, low target pressures
# Pot 2 @ 50% → normal prosthetic fit (matches old defaults)
# Pot 2 @ 100% → tight fit, high pressure tolerance

TARGET_MIN_KPA_AT_POT0 = 4.0
TARGET_MAX_KPA_AT_POT0 = 6.0
TARGET_MIN_KPA_AT_POT1 = 14.0
TARGET_MAX_KPA_AT_POT1 = 18.0

# Fallback when Arduino is disconnected
DEFAULT_TARGET_MIN_KPA = 8.0
DEFAULT_TARGET_MAX_KPA = 12.0

ADC_MAX = 1023  # 10-bit ADC

# ── Shared state (written by serial reader, read by telemetry + WS) ────

_pot1_value: float = 0.0       # Pot 1 normalized [0, 1]
_pot2_value: float = 0.5       # Pot 2 normalized [0, 1]
_target_range: tuple[float, float] = (DEFAULT_TARGET_MIN_KPA, DEFAULT_TARGET_MAX_KPA)
_arduino_connected: bool = False
_last_serial_ts: float = 0.0
_serial_task: Optional[asyncio.Task] = None
_latest_pot_ts: float = 0.0

# Pot event handler — registered by main.py lifespan to actually
# trigger the prosthetic cycle on threshold crossing. Signature:
#   async def handler(pot_value: float, ts: float) -> None
# The handler should call prosthetic_state.note_pot() and, if the
# crossing fires, kick off the full pipeline cycle.
_pot_event_handler: Optional[object] = None

# Broadcast callback — set by main.py during lifespan startup.
# Signature: async (payload: dict) -> None
_broadcast_fn: Optional[object] = None


def get_target_pressure_range() -> tuple[float, float]:
    """
    Return the current (min_kpa, max_kpa) target range.

    Called by :func:`telemetry.generate_target_array` instead of
    hard-coded constants.  Falls back to ``(8.0, 12.0)`` when the
    Arduino bridge is not active.
    """
    if not _arduino_connected:
        return (DEFAULT_TARGET_MIN_KPA, DEFAULT_TARGET_MAX_KPA)
    return _target_range


def is_arduino_connected() -> bool:
    """Whether the serial bridge has an active connection."""
    return _arduino_connected


def get_pot1_value() -> float:
    """Current Pot 1 value in [0, 1]."""
    return _pot1_value


def get_pot2_value() -> float:
    """Current Pot 2 value in [0, 1]."""
    return _pot2_value


def get_status() -> dict:
    """Full status dict for the ``/api/v1/arduino/status`` endpoint."""
    tmin, tmax = get_target_pressure_range()
    return {
        "connected": _arduino_connected,
        "port": PORT,
        "pot1": _pot1_value,
        "pot2": _pot2_value,
        "target_pressure_range": {"min_kpa": tmin, "max_kpa": tmax},
        "last_reading_ts": _last_serial_ts,
        "enabled": ENABLED,
    }


def set_broadcast_fn(fn) -> None:
    """Store the broadcast function from main.py for WS push."""
    global _broadcast_fn
    _broadcast_fn = fn


def set_pot_event_handler(fn) -> None:
    """
    Register the async pot-event handler used to fire the prosthetic
    cycle on threshold crossing.  Signature:

        async def handler(pot_value: float, ts: float) -> None
    """
    global _pot_event_handler
    _pot_event_handler = fn


def _pot2_to_range(pot2_norm: float) -> tuple[float, float]:
    """Map a normalized pot2 value to a (min_kpa, max_kpa) range."""
    t = max(0.0, min(1.0, pot2_norm))
    min_kpa = TARGET_MIN_KPA_AT_POT0 + (TARGET_MIN_KPA_AT_POT1 - TARGET_MIN_KPA_AT_POT0) * t
    max_kpa = TARGET_MAX_KPA_AT_POT0 + (TARGET_MAX_KPA_AT_POT1 - TARGET_MAX_KPA_AT_POT0) * t
    return (round(min_kpa, 2), round(max_kpa, 2))


async def _broadcast(payload: dict) -> None:
    """Fire the broadcast callback if available."""
    if _broadcast_fn is not None:
        try:
            await _broadcast_fn(payload)
        except Exception:
            pass  # never block the serial loop


async def _serial_reader() -> None:
    """
    Background coroutine — open the serial port, read CSV lines,
    update shared state, and fire prosthetic cycles.

    Auto-reconnects on disconnect / read timeout.
    """
    global _pot1_value, _pot2_value, _target_range
    global _arduino_connected, _last_serial_ts

    import serial
    import serial.asyncio

    log.info("Arduino serial bridge starting on %s @ %d baud", PORT, BAUD)

    while True:
        ser = None
        try:
            ser = serial.Serial(PORT, BAUD, timeout=READ_TIMEOUT)
            _arduino_connected = True
            _last_serial_ts = time.time()
            log.info("Arduino connected on %s", PORT)

            await _broadcast({
                "type": "arduino_status",
                "connected": True,
                "pot1": _pot1_value,
                "pot2": _pot2_value,
            })

            # Let the Arduino settle after port open (it resets on DTR).
            await asyncio.sleep(1.5)

            while True:
                # Non-blocking read loop using asyncio sleep
                raw = ser.readline()
                if not raw:
                    # Timeout — check if stale
                    if time.time() - _last_serial_ts > READ_TIMEOUT * 3:
                        log.warning("Arduino read stale — reconnecting...")
                        break
                    await asyncio.sleep(0.01)
                    continue

                line = raw.decode("ascii", errors="replace").strip()
                if not line:
                    continue

                try:
                    parts = line.split(",")
                    if len(parts) != 2:
                        continue
                    raw1 = int(parts[0])
                    raw2 = int(parts[1])
                except (ValueError, IndexError):
                    continue

                # Normalize to [0, 1]
                pot1_norm = max(0.0, min(1.0, raw1 / ADC_MAX))
                pot2_norm = max(0.0, min(1.0, raw2 / ADC_MAX))

                _pot1_value = pot1_norm
                _pot2_value = pot2_norm
                _target_range = _pot2_to_range(pot2_norm)
                _last_serial_ts = time.time()
                _latest_pot_ts = time.time()

                # Trigger the prosthetic cycle on threshold crossing
                # (registers rising-edge logic via main.py's handler).
                if _pot_event_handler is not None:
                    try:
                        await _pot_event_handler(pot1_norm, _latest_pot_ts)
                    except Exception:
                        pass  # never block the serial loop

                # Broadcast pot1 as a prosthetic WS pot event
                # (this drives the existing prosthetic cycle via ProstheticState.note_pot)
                await _broadcast({
                    "type": "pot",
                    "value": pot1_norm,
                    "ts": _latest_pot_ts,
                    "source": "arduino",
                })

                # Broadcast the target pressure range so the HUD can display it
                await _broadcast({
                    "type": "target_pressure",
                    "pot2": pot2_norm,
                    "target_min_kpa": _target_range[0],
                    "target_max_kpa": _target_range[1],
                    "source": "arduino",
                })

                await asyncio.sleep(0.01)  # ~30 Hz budget

        except serial.SerialException as e:
            log.warning("Arduino serial error: %s — reconnecting in %.0fs", e, RECONNECT_DELAY)
        except Exception as e:
            log.exception("Arduino unexpected error: %s", e)

        finally:
            _arduino_connected = False
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass

            await _broadcast({
                "type": "arduino_status",
                "connected": False,
            })

        await asyncio.sleep(RECONNECT_DELAY)


async def start_arduino_bridge() -> Optional[asyncio.Task]:
    """
    Start the serial reader as a background task, if enabled.

    Returns the asyncio.Task (for cancellation on shutdown), or None
    if Arduino integration is disabled.
    """
    global _serial_task

    if not ENABLED:
        log.info("Arduino bridge disabled (ENABLE_ARDUINO != true)")
        return None

    _serial_task = asyncio.create_task(_serial_reader())
    return _serial_task


async def stop_arduino_bridge() -> None:
    """Cancel the serial reader task on shutdown."""
    global _serial_task
    if _serial_task is not None:
        _serial_task.cancel()
        try:
            await _serial_task
        except asyncio.CancelledError:
            pass
        _serial_task = None
        log.info("Arduino serial bridge stopped.")
