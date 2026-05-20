# ResoScan Firmware

> Hardware-side guide for the ResoScan handheld bone-resonance diagnostic. Written so a teammate joining the firmware side can read this once and know **what to build, what's done, what's negotiable, and what software needs from the device.**

---

## What the device does, in 3 lines

1. A **Voice Coil Actuator** taps the bone through the skin with a precise 20–200 Hz vibration.
2. A **MEMS accelerometer** on the other side of the bone listens to how it vibrates back.
3. The ESP32 turns that vibration into a **healing score (TSI)** and tells the surgeon whether the patient can walk yet.

That's the whole product. Everything below is the engineering to make it real.

---

## The big picture (hardware ↔ software)

```
   ┌──────────────────── DEVICE (you build) ────────────────────┐
   │                                                            │
   │   Voice Coil Actuator  ←── DAC + DMA chirp ──   ESP32-S3   │
   │           │                                       │  ▲     │
   │       (vibration into bone)                       │  │     │
   │           │                                       │  │     │
   │           ↓                                       │  │     │
   │       MEMS Accelerometer (IIS3DWB) ── SPI@10MHz ──┘  │     │
   │                                                      │     │
   │   Force sensor (FSR or HX711+load cell) ────── ADC ──┘     │
   │                                                            │
   └────────────────────────────┬───────────────────────────────┘
                                │ USB CDC @ 921 600 baud
                                │ line-delimited JSON
                                ↓
   ┌─────────────────────── HOST (already built) ───────────────┐
   │                                                            │
   │   Python serial bridge → Streamlit simulator (backup demo) │
   │   Python serial bridge → Next.js dashboard (primary demo)  │
   │   Python ML inference, Gompertz days-to-walk prediction    │
   │                                                            │
   └────────────────────────────────────────────────────────────┘
```

You own everything inside the box. We own everything outside. The wire between them is one JSON object per scan over USB.

---

## What I (software side) need from you per scan

One JSON line over USB serial, like this. Bold fields are required for the system to function; everything else is polish:

```jsonc
{
  "type": "scan_result",
  "scan_id": 42,
  "device_id": "RS-PROTO-001",
  "fw_version": "0.2.1",
  "started_at_ms": 1736102345120,

  "chirp": {
    "type": "log",
    "f_start_hz": 20.0,
    "f_end_hz": 200.0,
    "duration_ms": 500,
    "amplitude_norm": 0.85
  },

  // raw waveform — for charts + so we can re-derive features ourselves
  "accel": {
    "axis": "z",
    "sample_rate_hz": 2667.0,
    "n_samples": 1024,
    "full_scale_g": 4.0,
    "samples_base64": "…"          // base64 of int16-LE buffer
  },

  // your firmware's computed verdict
  "features": {
    "f1_hz": 101.4,                // ← REQUIRED. The dominant frequency in 20-200 Hz
    "q_factor": 14.2,              // ← REQUIRED. f1 divided by its -3 dB bandwidth
    "damping_ratio": 0.035,        // ← REQUIRED. ζ via half-power bandwidth method
    "bandwidth_hz": 7.1,
    "secondary_peak_hz": null,     // ← REQUIRED if loose-implant detection runs
    "secondary_peak_ratio": 0.0,
    "snr_db": 28.4
  },

  // quality / safety gates
  "quality": {
    "preload_n": 3.4,              // ← REQUIRED. Force sensor reading at scan start
    "preload_ok": true,            // ← REQUIRED. Is it in the 2-5 N window?
    "saturated": false,
    "chirp_verified": true,
    "score": 0.94
  },

  // the bottom-line answer the device gives the clinician
  "verdict": {
    "tsi_pct": 88.4,               // ← REQUIRED. (f1 / f_healthy)² × 100
    "f_healthy_hz": 108.0,         // ← REQUIRED. From NVS contralateral-limb calibration
    "classification": "Stable",    // "Stable" | "Delayed Union" | "Non-Union" | "Implant Failure"
    "traffic_light": "green",      // "green" | "amber" | "red"
    "recommendation": "FULL_WEIGHT_BEARING"
  }
}
```

**Minimum payload that makes the dashboards work:**
- `accel.samples_base64` (so the host can draw charts and double-check your math)
- `features.f1_hz`, `features.q_factor`, `features.damping_ratio`
- `quality.preload_n`
- `verdict.tsi_pct`

Everything else is nice-to-have. **Full schema with all the rationale is in [`../docs/HARDWARE_INTERFACE_SPEC.md`](../docs/HARDWARE_INTERFACE_SPEC.md).**

---

## What else you need to emit besides the scan result

### On boot (once, when USB connects)

```jsonc
{
  "type": "hello",
  "device_id": "RS-PROTO-001",
  "fw_version": "0.2.1",
  "hw_revision": "rev-B",
  "capabilities": ["scan", "calibrate", "stream", "force"],
  "f_healthy_hz": 108.0,            // last calibrated baseline, or null
  "self_test": "pass"
}
```

This is the handshake. Without it, the host shows "device disconnected."

### Every second (telemetry heartbeat)

```jsonc
{
  "type": "telemetry",
  "uptime_ms": 1042330,
  "battery_pct": 87,
  "battery_v": 3.92,
  "temperature_c": 28.5,
  "preload_n": 0.0,
  "ready": true
}
```

Drives the battery icon, the "device ready" indicator, and lets us spot a flat battery before the doctor does.

---

## What I send to you (host → device commands)

JSON over USB, one per line:

```jsonc
{ "cmd": "scan" }                                     // run one scan now
{ "cmd": "set_f_healthy", "value": 105.2 }            // store calibration
{ "cmd": "set_patient_id", "value": "P-2611" }
{ "cmd": "calibrate_offset" }                         // gravity at rest
{ "cmd": "ping" }                                     // health check
{ "cmd": "stream", "rate_hz": 2667, "duration_ms": 2000 }  // continuous debug
```

Acknowledge each command within 50 ms with either `{ "type":"ack", ... }` or `{ "type":"err", "reason":"..." }`.

---

## Hardware components (current choice)

| Part | Spec | Where |
|---|---|---|
| **MCU** | ESP32-S3 (dual-core, USB CDC native, has DAC) | dev kit fine for prototype; custom PCB later |
| **Accelerometer** | STMicro IIS3DWB (3-axis, 26.7 kHz max ODR, SPI ≤ 10 MHz, 6-axis IMU if you read the gyro too) | Mouser / DigiKey, ~₹400 |
| **Actuator** | Voice Coil Actuator, peak force 10-15 N, stroke 5 mm, mass <20 g | MotiCont LVCM-019 for proto, custom-wound for production |
| **Amplifier** | Class-D mono amp (PAM8403 or similar) driven by DAC | breakout boards from Robu.in / Robokits |
| **Force sensor** | FSR402 (cheap, sufficient) or HX711 + 10 kg load cell (more precise) | preload measurement, **non-negotiable** |
| **Battery + PMIC** | Li-Po 2 000 mAh + TP4056 charger | enough for ~50 scans |
| **Coupling tip** | ZnO-doped silicone elastomer (cured Sylgard 184) | impedance-matched to skin |

---

## Wiring (ESP32-S3 pin assignments — already in `main/config.h`)

| Signal | GPIO | Notes |
|---|---|---|
| SPI MOSI | 11 | → IIS3DWB SDI |
| SPI MISO | 13 | ← IIS3DWB SDO |
| SPI SCLK | 12 | → IIS3DWB SCL |
| SPI CS | 10 | → IIS3DWB CS |
| SPI INT1 (DRDY) | 14 | ← IIS3DWB INT1 (data-ready IRQ) |
| DAC OUT | 17 | → Class-D amp input |
| AMP shutdown | 18 | active-low enable, GND to disable |
| Force ADC | 9 | ← FSR or HX711 |
| Scan LED | 2 | optional, status light |
| Done LED | 3 | optional |

Power: 3V3 to both IIS3DWB and amp board. Common ground everywhere. **Decouple the amp's supply with at least 100 µF + 0.1 µF close to the chip** — the chirp current pulses *will* couple noise into the accelerometer otherwise.

---

## What the firmware does on the chip (already coded in `main/`)

| Step | File | Status |
|---|---|---|
| Boot, NVS, FreeRTOS topology | `main.c` | ✅ done |
| Chirp generation via `dac_continuous` + DMA | `chirp_gen.c` | ✅ done |
| SPI master + ping-pong DMA reads of IIS3DWB | `sensor_spi.c` | ✅ done |
| esp_dsp 1024-pt FFT pinned to core 1 | `fft_task.c` | ✅ done |
| Peak detect + sub-bin parabolic interpolation | `fft_task.c` | ✅ done |
| TSI = (f₁ / f_healthy)² × 100 + classification | `stiffness.c` | ✅ done |
| ESP_LOG output of f₁ and TSI | `stiffness.c` | ✅ done |
| **JSON-over-USB output (the schema above)** | TODO | ⬜ **next thing to wire** |
| **Force sensor read + preload gate** | TODO | ⬜ **next thing to wire** |
| **NVS storage of `f_healthy_hz` + `device_id`** | TODO | ⬜ |
| **Host-command handler (read JSON from USB)** | TODO | ⬜ |
| **Boot `hello` + 1 Hz `telemetry`** | TODO | ⬜ |

The DSP backbone exists. What's missing is the **serial / JSON layer + force sensor + NVS** — the actual communication contract with the host. That's the next 1-2 days of firmware work.

---

## Things to decide together before you wire

These are real choices we should make as a team, not assumptions one side can make alone:

1. **JSON library on the MCU** — `cJSON` (10 KB, MIT, drop-in) is my default. OK with that? Or do you want to hand-roll `printf` formatting?
2. **Accelerometer axis** — schema currently says single Z-axis. Sending all 3 axes is trivial on the SPI side and 3× the bandwidth (~8 KB per scan, still fine). Want to ship 3-axis from v1?
3. **Scan burst vs single scan** — real instruments do 5 scans and report mean ± σ. Doing this in firmware adds ~2.5 s per scan but kills random noise. Worth it?
4. **Force sensor choice** — FSR402 is cheap and good enough for "is preload roughly OK?" gating. HX711 + load cell is overkill but gives us real grams. Which?
5. **BLE for v2** — we said USB tonight. When do we add BLE? After the demo?
6. **Sterilisation** — single-use silicone coupling caps vs reusable + alcohol wipe? UX implication.

Throw your opinions back at me in a message; we'll lock the answers in [`docs/HARDWARE_INTERFACE_SPEC.md`](../docs/HARDWARE_INTERFACE_SPEC.md).

---

## Build & flash

```bash
# One-time: set up ESP-IDF v5.1+
. $IDF_PATH/export.sh

# In firmware/
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor       # Windows: COM5/COM7  Linux: /dev/ttyUSB0  Mac: /dev/cu.SLAB*
```

First build downloads `esp_dsp` automatically (it's an IDF managed component).

---

## Sanity-check output on the serial monitor today

You should see this when you flash the current code:

```
I (220) resoscan: ==============================================
I (220) resoscan:  ResoScan firmware  v0.1
I (220) resoscan:  Physics target: f1 ~83 Hz (unhealed) -> ~101 Hz (healed)
I (240) resoscan:  Chirp band: 20 - 200 Hz (log sweep, 500 ms)
I (250) resoscan:  SPI 10 MHz, ODR 2667 Hz, FFT N=1024, bin=2.60 Hz
I (300) rs.fft:    fft_task init OK
I (310) rs.spi:    IIS3DWB WHOAMI 0x7B OK
I (350) rs.chirp:  init OK
I (1100) rs.stiff: f1=87.42 Hz  TSI=74.9%  -> PARTIAL weight-bearing
```

The `WHOAMI 0x7B OK` line means the IIS3DWB is wired correctly. The `TSI=…` line means the full DSP pipeline ran end-to-end. If you see both, you're good.

---

## Tunable parameters (config.h)

Everything is centralised in `main/config.h`. Touch this file, not the implementation files:

- `RS_CHIRP_F_START_HZ` / `RS_CHIRP_F_END_HZ` — sweep band (default 20 / 200 Hz)
- `RS_CHIRP_DURATION_MS` — sweep duration (default 500 ms)
- `RS_DAC_SAMPLE_RATE_HZ` — DAC output rate (default 8 kHz)
- `RS_ACCEL_SAMPLE_RATE_HZ` — IIS3DWB ODR (default 2 667 Hz)
- `RS_FFT_N` — FFT size (default 1024 → 2.6 Hz bin width)
- `RS_TIBIA_F_HEALTHY_HZ` — default healthy reference (per-patient override via NVS)
- `RS_TSI_FULL_WB_PCT` / `RS_TSI_PARTIAL_WB_PCT` — classification thresholds

---

## Where the rest of the project lives

- **[`../docs/HARDWARE_INTERFACE_SPEC.md`](../docs/HARDWARE_INTERFACE_SPEC.md)** — full JSON schema, every field explained
- **[`../docs/FIRMWARE_ARCHITECTURE.md`](../docs/FIRMWARE_ARCHITECTURE.md)** — FreeRTOS topology, DMA ping-pong, FFT details (the "why" behind every choice in `main/`)
- **[`../ortho_simulator/`](../ortho_simulator/)** — the Python reference implementation of the entire DSP + ML pipeline. If you ever wonder what a signal *should* look like, the simulator can generate it for you.
- **[`../docs/JURY_QA.md`](../docs/JURY_QA.md)** — anticipated tough questions and answers; doubles as a checklist of things judges will probe.

---

## In one paragraph: what to do this week

Wire the IIS3DWB and VCA per the pin table above. Flash the current code and confirm the `WHOAMI 0x7B OK` + `TSI=…` lines appear. Then **add the JSON-over-USB layer** so a `scan_result` line goes out every time a scan finishes — that single change unblocks the host team from synthetic data and lets us run the end-to-end demo on real silicon. The force sensor and NVS calibration come after.

Ping me when the JSON layer compiles. I'll write the Python serial bridge that reads it into the dashboards in parallel.
