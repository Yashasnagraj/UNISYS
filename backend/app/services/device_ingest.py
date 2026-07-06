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
import re
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
DEVICE_FS_HZ = 800.0          # nominal ODR; real EFFECTIVE rate is parsed per capture
_CAPTURE_HDR = "Z Capture Results"

# The firmware throttles to a far lower EFFECTIVE rate (print-per-sample), and
# reports it as e.g. "Actual Z rate: 28.9 Hz". We must use that as fs, not 800 —
# otherwise every derived frequency is off by ~28x.
_RATE_RE = re.compile(r"Actual Z rate:\s*([\d.]+)\s*Hz")

# Failed ADXL345 reads print as Z_raw=-1 (Z_mg=-3.9). These are dropouts, not
# real samples — drop/interpolate them, never feed -3.9 into the signal.
_DROPOUT_Z_RAW = -1.0
_MIN_VALID_SAMPLES = 48       # a real low-rate response window is short


def _clean_block(z_mg: list[float], z_raw: list[float]):
    """Turn one raw capture block into a clean sweep: trim leading/trailing
    dropout runs, linearly interpolate interior dropouts. Returns an np.ndarray
    (Z_mg) or None if too few valid samples. Dropouts are where Z_raw == -1."""
    if len(z_mg) < _MIN_VALID_SAMPLES:
        return None
    mg = np.asarray(z_mg, dtype=float)
    raw = np.asarray(z_raw, dtype=float)
    valid = raw != _DROPOUT_Z_RAW
    if int(valid.sum()) < _MIN_VALID_SAMPLES:
        return None
    first = int(np.argmax(valid))
    last = len(valid) - 1 - int(np.argmax(valid[::-1]))
    seg = mg[first:last + 1].copy()
    seg_valid = valid[first:last + 1]
    if not seg_valid.all():
        idx = np.arange(len(seg))
        seg[~seg_valid] = np.interp(idx[~seg_valid], idx[seg_valid], seg[seg_valid])
    return seg


def parse_capture_dump(text: str) -> dict:
    """Pure parser for a plain-text capture dump (one or more chirp blocks).

    Handles the real firmware format:
        Actual Z rate: 28.9 Hz
        ── Z Capture Results ──
        Sample<TAB>Z_raw<TAB>Z_mg
        0<TAB>-234<TAB>-912.6
        ...
    Uses the reported rate as fs, drops -1 dropout rows. Returns
    {'sweeps': list[list[float]], 'fs': float, 'source': 'device'}. Shared by the
    Wi-Fi/upload paths and the tests.
    """
    fs = DEVICE_FS_HZ
    sweeps: list[list[float]] = []
    cur_mg: list[float] = []
    cur_raw: list[float] = []
    in_block = False

    def _flush():
        nonlocal cur_mg, cur_raw
        cleaned = _clean_block(cur_mg, cur_raw)
        if cleaned is not None:
            sweeps.append(cleaned.tolist())
        cur_mg, cur_raw = [], []

    for line in text.splitlines():
        line = line.strip()
        m = _RATE_RE.search(line)
        if m:
            try:
                fs = float(m.group(1))
            except ValueError:
                pass
        if _CAPTURE_HDR in line:
            if in_block:
                _flush()
            in_block = True
            cur_mg, cur_raw = [], []
            continue
        if not in_block:
            continue
        if line.startswith("Sample"):
            continue
        parts = line.split()
        if len(parts) == 3:
            try:
                cur_raw.append(float(parts[1]))
                cur_mg.append(float(parts[2]))
                continue
            except ValueError:
                pass
        # any non-data line inside a block ends it
        _flush()
        in_block = False
    if in_block:
        _flush()
    return {"sweeps": sweeps, "fs": fs, "source": "device"}


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
        # NON-RESETTING open: dtr/rts False so opening the port does NOT reboot
        # the ESP32. A reboot knocks the ADXL345 into 0xFF, and this firmware
        # auto-chirps on its own — so we just listen for the next capture block
        # rather than reset + trigger.
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.dtr = False
        ser.rts = False
        ser.timeout = 0.3
        ser.open()
        time.sleep(0.2)
    except Exception as exc:
        result_q.put({"error": str(exc)})
        return

    sweeps: list[list[float]] = []
    cur_mg: list[float] = []
    cur_raw: list[float] = []
    parsed_rate: Optional[float] = None
    in_block = False
    adxl_ok = False
    chirp_pending = False        # a chirp was triggered, waiting for its data block
    pending_since = 0.0
    start = time.monotonic()
    saw_any = False              # any serial line yet?
    pulsed = False               # have we done the one-time recovery reset pulse?
    probe_start = time.monotonic()
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
            if raw:
                saw_any = True
            elif not saw_any and not pulsed and (now - probe_start) > 3.0:
                # Silent for 3 s -> the chip is likely held OFF (a prior close left
                # DTR high / RTS low) or idle. ONE clean reset pulse (EN low->high)
                # forces a fresh boot. NEVER repeat — rapid resets push the ADXL to
                # 0xFF. If the boot still comes up 0xFF, the ADXL wiring is the fault.
                try:
                    ser.dtr = True; ser.rts = False    # EN low: chip held off
                    time.sleep(0.12)
                    ser.dtr = False; ser.rts = False   # EN high: release -> boot
                except Exception:
                    pass
                pulsed = True
                start = time.monotonic()               # give the boot a full window
                ser.reset_input_buffer()
                continue
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

            # Capture the firmware's reported EFFECTIVE sample rate (printed just
            # before each block: "Actual Z rate: 28.9 Hz").
            m = _RATE_RE.search(line)
            if m:
                try:
                    parsed_rate = float(m.group(1))
                except ValueError:
                    pass

            # The firmware auto-chirps at boot and prints "Triggering" before each
            # capture. Mark the chirp pending; we must NOT send another trigger until
            # its block completes (a mid-chirp byte aborts the capture).
            if "Triggering" in line:
                chirp_pending = True
                pending_since = now
                continue

            if _CAPTURE_HDR in line:
                in_block = True
                cur_mg = []
                cur_raw = []
                continue
            if in_block:
                if line.startswith("Sample"):
                    continue
                parts = line.split()
                if len(parts) == 3:
                    try:
                        cur_raw.append(float(parts[1]))   # Z_raw (dropout marker)
                        cur_mg.append(float(parts[2]))    # Z_mg
                        continue
                    except ValueError:
                        pass
                # non-data line ends the block: clean dropouts + keep if valid
                cleaned = _clean_block(cur_mg, cur_raw)
                if cleaned is not None:
                    sweeps.append(cleaned.tolist())
                cur_mg, cur_raw = [], []
                in_block = False
                chirp_pending = False
                # Need more sweeps? Trigger the NEXT chirp now (block is done, so the
                # byte won't abort anything), then wait for it.
                if len(sweeps) < n_sweeps:
                    _kick()
                    chirp_pending = True
                    pending_since = now
    finally:
        # Leave DTR=False/RTS=False so the chip stays RUNNING after we close —
        # never leave it held in reset (DTR high / RTS low), which is what makes
        # the device go silent for the NEXT opener (incl. PuTTY).
        try:
            if ser.is_open:
                ser.dtr = False
                ser.rts = False
        except Exception:
            pass
        if ser.is_open:
            ser.close()

    if sweeps:
        result_q.put({"sweeps": sweeps, "fs": parsed_rate})
    else:
        result_q.put({"error": "0xFF" if not adxl_ok else "stalled"})


# ── Capture via a PuTTY (or any terminal) log file ──────────────────────────
#
# PuTTY holds the serial port reliably and can log every received byte to a
# file (Change Settings -> Logging -> "All session output"). We just read the
# newest complete capture block from that file. This sidesteps the COM-port
# reset/locking entirely — PuTTY is the reader, the log is the handoff.

def capture_from_log(path: str, n_sweeps: int = 1,
                     max_tail_bytes: int = 800_000) -> dict:
    """Read the most recent complete capture block(s) from a terminal log file.
    Returns {'sweeps': list[np.ndarray], 'fs': float, 'source': 'device'}."""
    if not path or not os.path.exists(path):
        raise DeviceUnavailableError(f"log file not found: {path!r}")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_tail_bytes))
        text = f.read()
    parsed = parse_capture_dump(text)
    if not parsed["sweeps"]:
        raise DeviceUnavailableError(
            "no complete capture block in the log yet — let PuTTY record one "
            "full chirp (~30 s) and try again")
    sweeps = parsed["sweeps"][-max(1, n_sweeps):]
    # blocks can differ in length (different dropout counts) — truncate to the
    # common length so they can be coherently averaged downstream.
    n_len = min(len(s) for s in sweeps)
    arr = [np.asarray(s[:n_len], dtype=float) for s in sweeps]
    return {"sweeps": arr, "fs": parsed["fs"], "source": "device"}


# ── Capture via the Wi-Fi CSV (tools/capture.py) ────────────────────────────
#
# The Wi-Fi firmware buffers a full 5 s sweep at the ADXL345 ODR (3200 Hz) and
# bursts it as "N,Z" lines (sample index, raw Z counts). tools/capture.py writes
# those to a CSV. Sample N was taken at time N / fs, so we reconstruct by index —
# any UDP-dropped sample is interpolated back into its correct time slot, keeping
# fs exact even with packet loss.

DEVICE_CSV_FS_HZ = 3200.0     # firmware ODR — sample N is at N/fs seconds
_MIN_CSV_SAMPLES = 512        # need at least one Welch window's worth


def _reconstruct_csv_sweep(pairs: list[tuple[int, float]]):
    """One sweep's (index, z) pairs → a gap-free array at uniform fs spacing.
    Missing indices (dropped UDP samples) are linearly interpolated. Returns an
    np.ndarray or None if too few valid samples."""
    if len(pairs) < _MIN_CSV_SAMPLES:
        return None
    max_n = max(n for n, _ in pairs)
    arr = np.full(max_n + 1, np.nan, dtype=float)
    for n, z in pairs:
        if 0 <= n <= max_n:
            arr[n] = z
    good = ~np.isnan(arr)
    if int(good.sum()) < _MIN_CSV_SAMPLES:
        return None
    if not good.all():
        idx = np.arange(max_n + 1)
        arr[~good] = np.interp(idx[~good], idx[good], arr[good])
    return arr


def capture_from_csv(path: str, fs: float = DEVICE_CSV_FS_HZ,
                     n_sweeps: int = 8) -> dict:
    """Read the newest sweep(s) from the Wi-Fi capture CSV (columns: N,Z).

    Multiple sweeps in one file are split where the index N restarts at 0 (each
    FSR press restarts N). Returns
    {'sweeps': list[np.ndarray], 'fs': fs, 'source': 'device'}.
    Raises DeviceUnavailableError if the file is missing or has no usable sweep.
    """
    if not path or not os.path.exists(path):
        raise DeviceUnavailableError(f"capture CSV not found: {path!r}")

    sweeps: list[np.ndarray] = []
    cur: list[tuple[int, float]] = []

    def _flush():
        nonlocal cur
        arr = _reconstruct_csv_sweep(cur)
        if arr is not None:
            sweeps.append(arr)
        cur = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or not line[0].isdigit():   # skip "N,Z" header + status text
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                n = int(parts[0])
                z = float(parts[1])
            except ValueError:
                continue
            if n == 0 and cur:      # index reset → a new sweep begins
                _flush()
            cur.append((n, z))
    _flush()

    if not sweeps:
        raise DeviceUnavailableError(
            f"no complete sweep in {path!r} yet — capture one full 5 s sweep "
            f"(>= {_MIN_CSV_SAMPLES} samples) and try again")

    sweeps = sweeps[-max(1, n_sweeps):]
    n_len = min(len(s) for s in sweeps)      # rectangular for coherent averaging
    arr = [np.asarray(s[:n_len], dtype=float) for s in sweeps]
    return {"sweeps": arr, "fs": fs, "source": "device"}


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
    fs: float = DEVICE_FS_HZ
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
            if r.get("fs"):                 # firmware-reported EFFECTIVE rate
                fs = float(r["fs"])
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
    return {"sweeps": arr, "fs": fs, "source": "device"}
