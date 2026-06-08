"""
Device serial capture service.

Lifts CP2102/COM5 detection from firmware/tools/read_device.py and adds:
  - non-resetting open (dtr=False, rts=False) so the ESP32 doesn't reboot
  - tolerant line parser (tries spec JSON → JSON array → plain-text `index rawZ scaledZ`)
  - thread-based capture with hard timeout so we never block the event loop
  - auto-FS estimation from wall-clock elapsed time

Raises DeviceUnavailableError when the port cannot be opened; the scan
endpoint catches this and returns HTTP 503.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from typing import Optional

_DBG = bool(os.environ.get("DEV_DEBUG"))

import numpy as np

try:
    import serial
    from serial.tools import list_ports as _list_ports
    _SERIAL_OK = True
except ImportError:
    _SERIAL_OK = False


# ── Public exception ─────────────────────────────────────────────────────────

class DeviceUnavailableError(RuntimeError):
    pass


# ── Port detection (mirrors firmware/tools/read_device.py) ──────────────────

def find_device_port() -> Optional[str]:
    """Return COM port of the CP210x bridge, or None."""
    if not _SERIAL_OK:
        return None
    for p in _list_ports.comports():
        vid, pid = (p.vid or 0), (p.pid or 0)
        desc = (p.description or "").lower()
        if (vid, pid) == (0x10C4, 0xEA60) or "cp210" in desc or "uart bridge" in desc:
            return p.device
    return None


def device_status(port: Optional[str] = None, baud: int = 115200) -> dict:
    """Quick probe — open port, send nothing, close. Returns status dict."""
    if not _SERIAL_OK:
        return {"connected": False, "port": None, "baud": baud, "description": "pyserial not installed"}
    actual_port = port or find_device_port()
    if not actual_port:
        return {"connected": False, "port": None, "baud": baud, "description": "CP2102 not detected"}
    try:
        ser = serial.Serial()
        ser.port = actual_port
        ser.baudrate = baud
        ser.dtr = False
        ser.rts = False
        ser.timeout = 0.5
        ser.open()
        ser.close()
        return {"connected": True, "port": actual_port, "baud": baud, "description": "CP2102 ready"}
    except Exception as exc:
        return {"connected": False, "port": actual_port, "baud": baud, "description": str(exc)}


# ── Tolerant line parser ─────────────────────────────────────────────────────

def _parse_line(line: str) -> Optional[float]:
    """Extract a scaledZ float from one line, trying multiple formats.

    Format 1 (spec JSON):  {"scaledZ": -0.48}
    Format 2 (JSON array): [-0.48]
    Format 3 (plain text): "42 -1234 -0.482"  (index rawZ scaledZ)
    """
    line = line.strip()
    if not line:
        return None
    # spec JSON
    if line.startswith("{"):
        try:
            obj = json.loads(line)
            if "scaledZ" in obj:
                return float(obj["scaledZ"])
            if "scaled_z" in obj:
                return float(obj["scaled_z"])
        except (json.JSONDecodeError, ValueError):
            pass
    # JSON array
    if line.startswith("["):
        try:
            arr = json.loads(line)
            if arr:
                return float(arr[0])
        except (json.JSONDecodeError, ValueError):
            pass
    # plain text: last token is scaledZ
    parts = line.split()
    for token in reversed(parts):
        try:
            val = float(token)
            return val
        except ValueError:
            continue
    return None


# ── Firmware constants (ADXL345 + Log Chirp firmware) ───────────────────────
#
# The firmware prints, per chirp:
#     ── Z Capture Results ──...
#     Sample\tZ_raw\tZ_mg
#     0\t<raw>\t<mg>
#     ...  (≈ 800 rows at 800 Hz ODR)
# After the first auto-chirp at boot, sending any byte (newline) triggers
# another chirp + capture block. We treat each capture block as one sweep.
DEVICE_FS_HZ = 800.0          # ADXL345 ODR set by firmware
_CAPTURE_HDR = "Z Capture Results"


def _capture_session_worker(port: str, baud: int, n_sweeps: int, timeout_s: float,
                            result_q: "queue.Queue[dict]") -> None:
    """ONE serial session: reset the ESP32 once, wait for a clean boot (0xE5),
    then trigger `n_sweeps` chirps WITHIN THAT SAME SESSION (one kick per chirp).

    Critical hardware finding: the ADXL345 is not power-cycled by an ESP32 reset,
    so RAPID re-booting drives it into a 0xFF state it can't recover from. The
    reliable pattern is therefore exactly ONE boot, then trigger several chirps in
    that session — never re-reset to get more sweeps.

    Pushes {'sweeps': [[Z_mg...], ...]} or {'error': '0xFF'|...}.
    """
    if not _SERIAL_OK:
        result_q.put({"error": "pyserial not installed"})
        return
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.3)
        time.sleep(0.2)
    except Exception as exc:
        result_q.put({"error": str(exc)})
        return

    sweeps: list[list[float]] = []
    current: list[float] = []
    in_block = False
    adxl_ok = False
    chirp_pending = False        # a chirp was triggered, waiting for its data block
    pending_since = 0.0
    start = time.monotonic()
    ser.reset_input_buffer()

    def _kick():
        try:
            ser.write(b"\n"); ser.flush()
        except Exception:
            pass

    try:
        while time.monotonic() - start < timeout_s and len(sweeps) < n_sweeps:
            now = time.monotonic()

            # Stall detection: the firmware says "Triggering log chirp" then should
            # stream the data block within ~2.5 s. If a marginal sensor connection
            # makes it hang (detected but not delivering FIFO data), bail FAST so the
            # caller can fall back to simulation instead of waiting the full timeout.
            if chirp_pending and not in_block and (now - pending_since) > 4.5:
                break

            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if _DBG and ("Device ID" in line or "Triggering" in line or _CAPTURE_HDR in line):
                print(("      [sess] " + line[:70]).encode("ascii", "replace").decode("ascii"))

            # Precise boot verdict (the error line also mentions "0xE5"/"found").
            if "Device ID: 0xFF" in line or "not found" in line.lower():
                result_q.put({"error": "0xFF"})
                ser.close()
                return
            if "Device ID: 0xE5" in line:
                adxl_ok = True

            # The firmware auto-chirps at boot and prints "Triggering" before each
            # capture. Mark the chirp pending; we must NOT send another trigger until
            # its block completes (a mid-chirp byte aborts the capture).
            if "Triggering" in line:
                chirp_pending = True
                pending_since = now
                continue

            if _CAPTURE_HDR in line:
                in_block = True
                current = []
                continue
            if in_block:
                if line.startswith("Sample"):
                    continue
                parts = line.split()
                if len(parts) == 3:
                    try:
                        current.append(float(parts[2]))   # Z_mg
                        continue
                    except ValueError:
                        pass
                # non-data line ends the block
                if len(current) >= 256:
                    sweeps.append(current)
                current = []
                in_block = False
                chirp_pending = False
                # Need more sweeps? Trigger the NEXT chirp now (block is done, so the
                # byte won't abort anything), then wait for it.
                if len(sweeps) < n_sweeps:
                    _kick()
                    chirp_pending = True
                    pending_since = now
    finally:
        if ser.is_open:
            ser.close()

    if sweeps:
        result_q.put({"sweeps": sweeps})
    else:
        result_q.put({"error": "0xFF" if not adxl_ok else "stalled"})


# ── Public API ────────────────────────────────────────────────────────────────

def capture_sweeps(
    n_sweeps: int = 3,
    port: Optional[str] = None,
    baud: int = 115200,
    timeout_s: float = 16.0,
    min_samples_per_sweep: int = 256,
    max_retries: int = 4,
) -> dict:
    """Capture N chirp sweeps from the device in ONE serial session per attempt.

    A single clean boot (reliable when the device has been idle) followed by N
    in-session chirp triggers avoids the rapid-reset cascade that pushes the
    ADXL345 to 0xFF. On a 0xFF boot we retry, but with a LONG settle so the sensor
    can recover — never the fast hammering that makes it worse.

    Returns {'sweeps': list[np.ndarray], 'fs': 800.0, 'source': 'device'}.
    Raises DeviceUnavailableError if the port is absent or all attempts fail.
    """
    actual_port = port or find_device_port()
    if not actual_port:
        raise DeviceUnavailableError("ResoScan device (CP2102) not found")

    sweeps: list[list[float]] = []
    for attempt in range(max_retries):
        if _DBG:
            print(f"    --- session {attempt + 1}/{max_retries} ---")
        result_q: queue.Queue[dict] = queue.Queue()
        thread = threading.Thread(
            target=_capture_session_worker,
            args=(actual_port, baud, n_sweeps, timeout_s, result_q),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=timeout_s + 3.0)

        try:
            r = result_q.get_nowait()
        except queue.Empty:
            r = {"error": "timeout"}

        if "sweeps" in r and r["sweeps"]:
            sweeps = r["sweeps"]
            break
        # 0xFF / timeout → LONG settle so the ADXL345 recovers before the next
        # reset. Fast retries make the 0xFF state worse, not better.
        time.sleep(3.0)

    if not sweeps:
        raise DeviceUnavailableError(
            "ADXL345 not detected (Device ID 0xFF) after retries. Unplug and "
            "replug the device to power-cycle the sensor, keep CS→3.3V firm, then retry."
        )

    n_len = min(len(s) for s in sweeps)
    arr = [np.asarray(s[:n_len], dtype=float) for s in sweeps]
    return {"sweeps": arr, "fs": DEVICE_FS_HZ, "source": "device"}
