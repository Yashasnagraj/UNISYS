"""
Batch raw-sweep recorder for the ResoScan device.

Reuses the production capture path (`app.services.device_ingest.capture_sweeps`)
to accumulate many clean sweeps across several boot sessions and write them to a
JSON fixture that can be replayed through the pipeline offline:

    backend/fixtures/<name>.json = {"fs": 800.0, "sweeps": [[...], ...], "meta": {...}}

Why sessions: the ADXL345 is not power-cycled by an ESP32 reset, so we capture a
handful of chirps per boot (one-boot-many-chirps) and settle between sessions
rather than hammering resets (which drives the sensor to a 0xFF state). Progress
is saved after every session, so a flaky sensor still yields a usable fixture.

Usage (run from the backend/ directory):
    python -m tools.capture_batch --name yashas_tibia --target 40
    python -m tools.capture_batch --name yashas_healthy --target 20   # contralateral baseline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Allow running as `python -m tools.capture_batch` or `python tools/capture_batch.py`
# from the backend/ directory: ensure the backend root is importable.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.services.device_ingest import (  # noqa: E402
    DeviceUnavailableError, capture_sweeps, device_status,
)

FIXTURES_DIR = os.path.join(_BACKEND_ROOT, "fixtures")

# Chirps per boot session — kept small so one healthy boot delivers them all
# without a mid-session sensor stall; more sweeps come from more sessions.
SWEEPS_PER_SESSION = 4
# Settle between boot sessions so the ADXL345 recovers before the next reset.
SESSION_SETTLE_S = 4.0


def _fixture_path(name: str) -> str:
    return os.path.join(FIXTURES_DIR, f"{name}.json")


def _save(path: str, fs: float, sweeps: list[list[float]], meta: dict) -> None:
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    meta = {**meta, "n_sweeps": len(sweeps)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"fs": fs, "sweeps": sweeps, "meta": meta}, fh)


def capture_batch(name: str, target: int, port: str | None, baud: int,
                  max_sessions: int) -> int:
    path = _fixture_path(name)
    status = device_status(port=port, baud=baud)
    if not status.get("connected"):
        print(f"  device not ready: {status.get('description')}")
        raise DeviceUnavailableError(status.get("description", "device not found"))
    print(f"  device: {status.get('port')} @ {baud}  ({status.get('description')})")

    fs: float = 800.0
    collected: list[list[float]] = []
    session = 0
    while len(collected) < target and session < max_sessions:
        session += 1
        need = min(SWEEPS_PER_SESSION, target - len(collected))
        print(f"  session {session}: requesting {need} sweeps "
              f"({len(collected)}/{target} so far)...")
        try:
            data = capture_sweeps(n_sweeps=need, port=port, baud=baud,
                                  timeout_s=16.0, max_retries=2)
            fs = float(data["fs"])
            for sweep in data["sweeps"]:
                collected.append([float(x) for x in sweep])
            _save(path, fs, collected, {"name": name, "port": status.get("port"), "baud": baud})
            print(f"    +{len(data['sweeps'])} sweeps  ->  saved {len(collected)} total")
        except DeviceUnavailableError as exc:
            print(f"    session failed ({exc}); settling {SESSION_SETTLE_S}s and retrying...")
        time.sleep(SESSION_SETTLE_S)

    if not collected:
        raise DeviceUnavailableError("no sweeps captured across all sessions")
    print(f"\n  DONE: {len(collected)} sweeps @ {fs:.0f} Hz -> {path}")
    return len(collected)


def main() -> None:
    ap = argparse.ArgumentParser(description="Record raw device sweeps to a replay fixture.")
    ap.add_argument("--name", required=True, help="fixture name (writes backend/fixtures/<name>.json)")
    ap.add_argument("--target", type=int, default=40, help="number of sweeps to accumulate")
    ap.add_argument("--port", default=None, help="serial port (auto-detect if omitted)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--max-sessions", type=int, default=30, help="safety cap on boot sessions")
    args = ap.parse_args()

    try:
        capture_batch(args.name, args.target, args.port, args.baud, args.max_sessions)
    except DeviceUnavailableError as exc:
        print(f"\n  ABORTED: {exc}")
        print("  Unplug/replug the device to power-cycle the ADXL345, keep CS->3.3V firm, retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
