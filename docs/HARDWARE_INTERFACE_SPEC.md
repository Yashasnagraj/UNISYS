# ResoScan — Hardware ↔ Software Interface Spec

> **For the hardware team.** This document defines exactly what the firmware must produce so that the Streamlit simulator, the Next.js clinical dashboard, and the trained ML model can consume real device output without code changes.

## TL;DR — what we need from each scan

A single scan = a single JSON line sent over **USB serial (921 600 baud, LF-terminated)** with the following structure:

```jsonc
{
  "type":              "scan_result",
  "scan_id":           42,                  // monotonically increasing per power-up
  "device_id":         "RS-PROTO-001",      // unique device serial, from NVS
  "fw_version":        "0.2.1",
  "started_at_ms":     1736102345120,       // millis() since RTC sync, or boot
  "duration_ms":       500,                 // total scan time

  // ── Stimulus the device delivered ────────────────────────────────
  "chirp": {
    "type":            "log",               // "log" | "linear" | "impulse"
    "f_start_hz":      20.0,
    "f_end_hz":        200.0,
    "amplitude_norm":  0.85,                // 0..1 of DAC range
    "duration_ms":     500
  },

  // ── What the device measured (raw) ───────────────────────────────
  "accel": {
    "axis":            "z",                 // "x" | "y" | "z" | "xyz"
    "sample_rate_hz":  2667.0,
    "n_samples":       1024,
    "full_scale_g":    4.0,
    "encoding":        "int16_le_base64",   // see "Payload encoding"
    "samples_base64":  "…"                  // base64 of int16 LE buffer
  },

  // ── Pre-computed on-device features (firmware's verdict) ─────────
  "features": {
    "f1_hz":               101.4,           // dominant peak in 20..200 Hz band
    "f1_sub_bin_hz":       101.42,          // parabolic interp for sub-bin
    "peak_power":          0.873,           // normalised PSD value at f1
    "q_factor":            14.2,            // f1 / -3dB bandwidth
    "bandwidth_hz":        7.1,             // -3dB bandwidth
    "damping_ratio":       0.035,           // ζ via half-power method
    "log_decrement":       0.219,           // log-dec from time-domain peaks
    "mdf":                 0.0349,          // modal damping factor
    "secondary_peak_hz":   null,            // null OR Hz if loose-implant rattle
    "secondary_peak_ratio": 0.0,            // 2nd peak / 1st peak power
    "snr_db":              28.4             // signal-to-noise estimate
  },

  // ── Quality / safety ─────────────────────────────────────────────
  "quality": {
    "preload_n":      3.4,                  // force sensor reading at scan start
    "preload_ok":     true,                 // in 2..5 N window?
    "saturated":      false,                // accel hit ±FS at any sample
    "chirp_verified": true,                 // amp drew expected current
    "score":          0.94                  // 0..1 overall scan-quality score
  },

  // ── On-device clinical decision (firmware's recommendation) ──────
  "verdict": {
    "tsi_pct":             88.4,            // (f1/f_healthy)² × 100
    "f_healthy_hz":        108.0,           // per-patient from NVS calibration
    "classification":      "Stable",        // see schema
    "traffic_light":       "green",         // "green"|"amber"|"red"
    "recommendation":      "FULL_WEIGHT_BEARING"
  }
}
```

If you do not implement everything below in the first prototype, the **bolded fields are the must-haves**:

- **`accel.samples_base64`** — raw waveform. Without this, host-side visualisations break.
- **`features.f1_hz`**, **`features.q_factor`**, **`features.damping_ratio`** — minimum for the AI to classify.
- **`quality.preload_n`** — without this we cannot reject bad scans.
- **`verdict.tsi_pct`** — the headline clinical number.

Everything else is optional polish.

---

## Why these specific signals

Each row is a row in the ML feature vector or a chart line in the UI:

| Field | Used by | Why we need it |
|---|---|---|
| `accel.samples_base64` | Streamlit waveform + spectrogram charts; recomputable host-side PSD | The visuals on the demo *are* the device. Raw waveform is the source of truth. |
| `features.f1_hz` | TSI, dashboard hero number, ML feature #1 | The fundamental flexural frequency is the single most important measurement. |
| `features.q_factor` | "How sharp the resonance is" metric + ML feature #7 | A sharper peak means a stiffer (more healed) bone. |
| `features.damping_ratio` (ζ) | Clinical metrics grid + ML feature #20 | Damping drops as the bone consolidates. |
| `features.secondary_peak_*` | Loose-implant detection + Implant-Failure class | A second peak ≈ FN/2 is the signature of loose surgical hardware. |
| `quality.preload_n` | Scan-rejection gate, soft-tissue artefact mitigation | Without 2-5 N preload the bone is not properly coupled to the probe. Industry standard. |
| `quality.snr_db` | Signal-quality dots in the UI, scan-rejection threshold | Sub-15 dB scans get rejected before the AI sees them. |
| `verdict.tsi_pct` | Headline number on every page | This is what the clinician reads. f² ∝ k. |

---

## What the firmware computes (versus what the host computes)

Firmware ESP32 already does this work in `firmware/main/*.c`:

| Step | Owner | Implemented in |
|---|---|---|
| Chirp generation 20-200 Hz log sweep via DAC + I2S DMA | **Firmware** | `chirp_gen.c` |
| SPI master @ 10 MHz reading IIS3DWB, DMA ping-pong | **Firmware** | `sensor_spi.c` |
| 1024-point FFT (esp_dsp `dsps_fft2r_fc32`) + Hanning window | **Firmware** | `fft_task.c` |
| Peak detection in 20-200 Hz band + sub-bin parabolic interpolation | **Firmware** | `fft_task.c` |
| Half-power bandwidth → Q-factor + ζ | **Firmware** (add) | `fft_task.c` |
| TSI computation = (f1 / f_healthy)² × 100 | **Firmware** | `stiffness.c` |
| Classification rule-base (Stable / Delayed / Non-union / Implant) | **Firmware** | `stiffness.c` |
| ML inference (RandomForest, 25 features) | **Host (Python/JS)** | `engine/classification.py` |
| Days-to-walk Gompertz fit over scan history | **Host** | `engine/healing_prediction.py` |
| Charts, animations, patient timeline | **Host** | dashboard |

The principle: **the device computes a verdict; the host produces the story** (charts, history, projections, narrative). The host can re-derive everything from the raw waveform — sending it is what gives us insurance against firmware bugs and lets us improve algorithms without re-flashing.

---

## Payload encoding

### Why base64 of raw int16 samples (not JSON arrays)

1024 samples × ~12 chars each (JSON array of int16) = ~12 KB of ASCII per scan. Slow to transmit and parse. Base64 of the raw bytes is ~2.7 KB and decodes in microseconds in Python/JS.

```c
// firmware side
const int16_t *buf;          // 1024 samples already in DMA buffer
size_t n = RS_FFT_N;
base64_encode((const uint8_t *)buf, n * sizeof(int16_t), payload_buf);
```

```python
# host side
import base64, numpy as np
samples = np.frombuffer(base64.b64decode(payload["accel"]["samples_base64"]),
                        dtype=np.int16)
gravity = samples.astype(np.float32) * payload["accel"]["full_scale_g"] / 32768.0
```

If base64 is annoying on the firmware side, **alternative**: send the same buffer over a binary frame (see "Transport" below) and keep JSON for everything else.

### JSON wire format

- One JSON object per line. LF (`\n`) terminator.
- No multi-line JSON. No comments in the wire payload.
- All numbers in SI units. Frequencies in Hz. Forces in Newtons. Times in milliseconds.
- Booleans as `true` / `false`, not 0 / 1.
- Use `null` for "not measured this scan" — never `0` or empty string.

---

## Transport

**Primary: USB CDC serial.**

```
Baud:      921 600
Data bits: 8N1
Flow ctrl: none
Framing:   line-delimited JSON (\n)
```

The ESP32 USB CDC stack at 921 600 baud comfortably carries one scan (~3 KB) in under 30 ms. We do not need anything faster for tonight's pipeline.

**Optional: BLE for phone pairing.**

- GATT service UUID `0xResoScan` (TBD)
- Characteristic `scan_result` (notify, ≤ 512 bytes payload, chunked) for the JSON
- Characteristic `cmd` (write) for host → device commands

BLE is a v2 feature. The dashboard for tonight reads from USB.

---

## Commands from host → device

For demo control. Send as JSON lines too, one object per line:

```jsonc
{ "cmd": "scan" }                                       // run one scan now
{ "cmd": "set_f_healthy", "value": 105.2 }              // store contralateral-limb reference
{ "cmd": "set_patient_id", "value": "P-2611" }
{ "cmd": "ping" }                                       // health check; replies with status
{ "cmd": "calibrate_offset" }                           // record gravity offset at rest
{ "cmd": "set_chirp",  "f_start_hz": 20, "f_end_hz": 200, "ms": 500 }
{ "cmd": "stream", "axes": "z", "rate_hz": 2667, "duration_ms": 2000 }
                                                        // continuous raw stream for debug
```

Device acknowledges every command within 50 ms:

```jsonc
{ "type": "ack", "cmd": "scan", "scan_id": 43 }
{ "type": "err", "cmd": "set_f_healthy", "reason": "out_of_range" }
```

---

## Continuous telemetry (between scans)

Every 1 s, fire a heartbeat:

```jsonc
{
  "type":         "telemetry",
  "device_id":    "RS-PROTO-001",
  "uptime_ms":    1042330,
  "battery_pct":  87,
  "battery_v":    3.92,
  "temperature_c": 28.5,
  "preload_n":    0.0,           // current force reading even when not scanning
  "ready":        true           // false while booting / self-test / fault
}
```

The dashboard can use this to surface a "device ready" indicator and a battery icon.

---

## Boot sequence — what the host expects

On power-up (or USB connect), the firmware should immediately emit:

```jsonc
{
  "type":         "hello",
  "device_id":    "RS-PROTO-001",
  "fw_version":   "0.2.1",
  "hw_revision":  "rev-B",
  "compiled_at":  "2026-05-20T11:32:00Z",
  "capabilities": ["scan", "calibrate", "stream", "ble", "force"],
  "f_healthy_hz": 108.0,         // last-stored contralateral baseline (or null)
  "self_test":    "pass"         // "pass" | "warn" | "fail"
}
```

That lets the host know the device is alive and what it can do.

---

## Calibration workflow

1. Patient sits, device is placed on their **healthy contralateral limb**.
2. Host sends `{ "cmd": "scan", "tag": "calibration" }`.
3. Device responds with a normal `scan_result`; its `features.f1_hz` is treated as the new `f_healthy_hz`.
4. Host sends `{ "cmd": "set_f_healthy", "value": 105.2 }`.
5. Device stores in NVS and uses for all subsequent injured-limb scans.

This is the gold-standard clinical approach (Cunningham 1990). It normalises out everything we can't measure (bone length, density, soft-tissue thickness).

---

## Quality gates (firmware should enforce these — host trusts them)

| Condition | Action |
|---|---|
| `preload_n < 1.8` or `> 5.5` | Set `quality.preload_ok = false`, refuse to scan, emit `err: preload_out_of_range` |
| `accel.saturated == true` | Reduce amp gain, retry once, then flag |
| `snr_db < 12` | Set `quality.score < 0.5`; host should de-emphasise the result |
| `chirp_verified == false` | Set `verdict.recommendation = "RESCAN_REQUIRED"` |
| Battery < 10% | Refuse to scan; emit `err: low_battery` |

---

## What we do NOT need from hardware

Skip these unless you have time:

- Three-axis accelerometer data (single Z-axis is enough for the bone's longitudinal mode)
- IMU orientation (gyro / magnetometer) — clinician already positions the probe
- Continuous streaming during normal operation (only debug uses `cmd: stream`)
- On-device wave-velocity ToF computation (Phase-2 feature for bladder/pulmonary)
- SD-card logging (host stores everything)
- Over-the-air firmware updates (we'll flash by USB during dev)

---

## Implementation checklist for the hardware team

If you do all of these, the dashboards work with **zero software changes**:

- [ ] Define and document the **JSON schema above** in your firmware (use a small json helper like `cJSON`)
- [ ] Add base64 helper for the accel buffer (or implement binary frames if preferred)
- [ ] USB CDC at 921 600 baud, line-buffered JSON output
- [ ] One `{type: "hello", …}` on boot
- [ ] One `{type: "telemetry", …}` per second
- [ ] One `{type: "scan_result", …}` per `cmd: scan`
- [ ] Implement the four quality gates above
- [ ] Compute on-device: `f1_hz`, `q_factor`, `damping_ratio`, `tsi_pct`, `classification`
- [ ] Send raw `accel.samples_base64` for every scan (1024 int16 samples = ~2.7 KB base64)
- [ ] Read force sensor at scan start, populate `quality.preload_n`
- [ ] Store `f_healthy_hz` in NVS, honour `set_f_healthy` command
- [ ] Store `device_id` in eFuse or NVS at manufacture

---

## How the host parses this

Python (Streamlit / engine side):

```python
import json, base64, numpy as np, serial
ser = serial.Serial("COM7", 921600, timeout=2)
ser.write(b'{"cmd":"scan"}\n')
for line in ser:
    msg = json.loads(line)
    if msg.get("type") == "scan_result":
        samples = np.frombuffer(
            base64.b64decode(msg["accel"]["samples_base64"]),
            dtype=np.int16,
        ).astype(np.float32) * msg["accel"]["full_scale_g"] / 32768.0
        # samples is now in g — feed into engine.fft_engine.full_spectral_analysis
        break
```

JavaScript (Next.js dashboard, when we add Web Serial in v2):

```ts
const port = await navigator.serial.requestPort();
await port.open({ baudRate: 921600 });
// read lines, JSON.parse, dispatch into the Zustand store
```

---

## Roadmap

**Tonight (must-have)**: the JSON schema above and the firmware code in `firmware/main/*.c` are already in the repo. Both teams can lock the schema before any wiring.

**This week**: hardware completes the per-scan emission. Host adds a `serial-bridge` Python helper that reads device output and forwards into the existing Streamlit + Next.js pipelines.

**Pre-finals**: end-to-end live demo from device → host → dashboard. The dashboards do not need to know whether their data is real or synthetic; the format is identical either way.

---

## Owners

- **Hardware / firmware:** owns the firmware in `firmware/main/*.c`, the JSON emitter, the quality gates.
- **Software / AI:** owns everything in `ortho_simulator/engine/`, `ortho_simulator/ml/`, and `web/`. Consumes the JSON.
- **Glue:** a small Python serial bridge (`tools/serial_bridge.py`, ~50 lines) — either team can own this.

If anything in this spec is unclear, push back on it before you wire — changing the contract after hardware is built is the expensive part.
