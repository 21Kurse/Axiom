"""End-to-end smoke test for /ws/prosthetic.

Connects, sends pot drags, observes the full event stream.
"""

import asyncio
import json
import sys
import time

import websockets


async def main_async():
    uri = "ws://127.0.0.1:8081/ws/prosthetic"
    events_seen = []
    cell_frames = 0
    diagnosis = None
    cycle_starts = 0

    async with websockets.connect(uri) as ws:
        print(f"=> connected to {uri}")

        initial = json.loads(await ws.recv())
        events_seen.append(initial.get("type"))
        print(f"   {initial.get('type')}: {initial.get('phase')}")

        await asyncio.sleep(0.3)

        async def drag(values):
            ts_start = time.time()
            for v in values:
                await ws.send(json.dumps({
                    "type": "pot",
                    "value": v,
                    "ts": ts_start + (time.time() - ts_start),
                }))
                await asyncio.sleep(0.04)

        await drag([0.05, 0.10, 0.15, 0.20])
        await drag([0.30, 0.35, 0.45, 0.55, 0.65, 0.73])

        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                break
            data = json.loads(raw)
            t = data.get("type")
            events_seen.append(t)
            if t == "cell_state":
                cell_frames += 1
                if cell_frames <= 2 or cell_frames % 5 == 0:
                    phase = data.get("phase")
                    frame = data.get("frame")
                    n = len(data.get("cells") or [])
                    print(f"   cell_state #{cell_frames} phase={phase} frame={frame} cells={n}")
            elif t == "diagnosis":
                diagnosis = data["data"]
                print(f"   diagnosis: conf={data['data'].get('confidence')} n_corr={data['data'].get('n_corrections')}")
            elif t == "status":
                phase = data.get("phase")
                print(f"   status -> {phase}")
                if phase == "DRIFT_INJECTING":
                    cycle_starts += 1
            elif t == "heatmap":
                print(f"   heatmap path -> {data.get('path')}")

        await ws.send(json.dumps({"type": "reset"}))
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
            data = json.loads(raw)
            print(f"   reset echo -> {data}")
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            pass

    print()
    print("=" * 50)
    print(f"events_seen (sample): {events_seen[:30]}")
    print(f"total cell_state frames: {cell_frames}")
    print(f"cycles fired (DRIFT_INJECTING count): {cycle_starts}")
    print(f"diagnosis seen: {bool(diagnosis)}")
    if diagnosis:
        print(f"diagnosis confidence: {diagnosis.get('confidence')}")
        print(f"diagnosis n_corrections: {diagnosis.get('n_corrections')}")
        ex = diagnosis.get("explanation") or ""
        print(f"diagnosis explanation head: {ex[:120]}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return asyncio.run(main_async())


if __name__ == "__main__":
    main()
