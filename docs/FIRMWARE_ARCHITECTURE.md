# ResoScan — Firmware Architecture

ESP32-S3 firmware refactor addressing three bottlenecks in the previous Arduino prototype: I2C bandwidth ceiling, blocking acquisition loops, and DMA packet drops under load.

## 1. Pipeline overview

```
            chirp_gen  (core 0, DAC continuous + DMA, 20-200 Hz log sweep)
                 |
                 v        Voice Coil  ==>  bone  ==>  vibration
                                                       |
                                                       v
       IIS3DWB <-- SPI master @ 10 MHz, DMA ping-pong, INT1 DRDY
                 |
                 v
       sensor_task  (core 0, producer, ping-pong + int16 -> float conversion)
                 |
                 v   FreeRTOS StreamBuffer (4 frames capacity)
                 |
                 v
          fft_task  (core 1, esp_dsp 1024-pt FFT + PSD + sub-bin peak interp)
                 |
                 v
        stiffness    (TSI = (f1 / f_healthy)^2 * 100, ESP_LOG / UART)
```

## 2. The two optimizations

### 2.1 Physics Pivot — 20 to 200 Hz fundamental-mode tracking

The previous design swept up to 700 Hz to capture higher-order harmonics. In practice the **fundamental flexural mode** $f_1$ is where:

- Published clinical literature places the tibial healing trajectory (~83 Hz unhealed → ~101 Hz healed; Cunningham 1990, Nakatsuchi 1996).
- SNR is highest (largest structural displacement at the fundamental).
- $f^2 \propto k$ stiffness coupling is cleanest (single mode, no harmonic interference).
- Tissue attenuation is lowest (lower frequencies penetrate soft tissue better).

Dropping the upper bound to 200 Hz removed the need for high-bandwidth VCA, halved battery drain during excitation, and eliminated the aliasing risk that the previous broadband sweep was flirting with.

### 2.2 Engineering Fix — SPI master + DMA + FreeRTOS dual-core

| | Previous (Arduino, blocking I2C) | Now (ESP-IDF, SPI + DMA + FreeRTOS) |
|---|---|---|
| Bus | I2C @ 400 kHz | SPI @ 10 MHz |
| Bus headroom at 2.667 kHz ODR | ~10× | ~250× |
| Acquisition pattern | polled, CPU blocks | DMA ping-pong, ISR-driven |
| DSP | runs on same core, contends with comms | pinned to core 1, isolated |
| Frame loss under load | observed | none expected |

## 3. FreeRTOS task topology

| Task | Core | Priority | Stack | Role |
|---|---|---|---|---|
| `app_main` | 0 (default) | – | IDF default | Init + scan trigger loop |
| `rs_sensor` | 0 | 10 | 4 KB | SPI master, DMA ping-pong, push to stream buffer |
| `rs_fft` | 1 | 9 | 6 KB | esp_dsp FFT, peak detection, hand off to stiffness |
| (chirp DMA) | – | hardware | – | Runs via dac_continuous DMA descriptors, no task |

**Inter-task synchronisation**: a single `StreamBufferHandle_t` (4 frames × 4 KB float) carries data from sensor → FFT. FreeRTOS provides thread-safety on this primitive natively — no manual mutex.

**ISR → task handoff** uses the ESP-IDF v5 idiom:

```c
static IRAM_ATTR bool on_dac_done_cb(...)
{
    BaseType_t hpw = pdFALSE;
    xSemaphoreGiveFromISR(s_done_sem, &hpw);
    return hpw == pdTRUE;          // dac_continuous handles YIELD
}
```

For sensor-side ISR notifications the equivalent pattern is:

```c
BaseType_t hpw = pdFALSE;
vTaskNotifyGiveFromISR(fft_task_handle, &hpw);
portYIELD_FROM_ISR(hpw);
```

## 4. DMA buffer strategy

```c
s_buf_a = (int16_t *)heap_caps_aligned_alloc(
    16, RS_DMA_BUF_BYTES, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
s_buf_b = (int16_t *)heap_caps_aligned_alloc(
    16, RS_DMA_BUF_BYTES, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
```

- **16-byte alignment** is the strictest ESP32 DMA requirement; satisfies SPI and any future I2S/I2S-DAC re-routing.
- `MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL` forces allocation in internal SRAM (PSRAM is not DMA-accessible for our use case).
- Two buffers, ping-pong: while DMA fills A, the producer task converts B to float and pushes; on next cycle they swap. The conversion + push always lags the fill by exactly one frame.

## 5. Memory budget

| Block | Size | Where |
|---|---|---|
| Chirp DMA buffer (8-bit DAC) | 4 KB | internal SRAM, DMA-capable |
| SPI DMA buffer A (int16 × 1024) | 2 KB | internal SRAM, DMA-capable |
| SPI DMA buffer B (int16 × 1024) | 2 KB | internal SRAM, DMA-capable |
| FFT Hann window (float × 1024) | 4 KB | internal SRAM |
| FFT complex working buf (float × 2048) | 8 KB | internal SRAM |
| FreeRTOS task stacks | ~14 KB | – |
| **Total** | **~34 KB** | well within ESP32-S3 512 KB SRAM |

No PSRAM required. Generous heap headroom for WiFi / BLE stack additions later.

## 6. FFT details

- **N = 1024 points**, single-precision (`float`), radix-2 (`dsps_fft2r_fc32`).
- At ODR 2 667 Hz: **bin width 2.6 Hz** — fine enough to resolve the ~18 Hz unhealed → healed spread.
- **Hanning window** via `dsps_wind_hann_f32` to suppress spectral leakage.
- **Sub-bin peak refinement** via quadratic interpolation on log-magnitudes of the three bins around the peak (Smith & Serra 1987). Effective resolution ≪ 1 Hz.
- Peak search restricted to [`RS_PEAK_SEARCH_LO_HZ`, `RS_PEAK_SEARCH_HI_HZ`] = [20, 200] Hz to ignore DC bias and out-of-band noise.

## 7. Stiffness calculation

```
TSI = (f1_smoothed / f_healthy)^2 × 100   [%]
```

with `f1_smoothed = 0.3 * f1_new + 0.7 * f1_prev` (exponential moving average to reject single-frame outliers).

Healing recommendations:

| TSI | Recommendation |
|---|---|
| ≥ 80% | Full weight-bearing |
| 60–79% | Partial weight-bearing |
| < 60% | Non weight-bearing |

`f_healthy` defaults to `RS_TIBIA_F_HEALTHY_HZ` (101 Hz) and can be overridden per patient via NVS for contralateral-limb calibration.

## 8. Why ESP-IDF (not Arduino-ESP32)

| Capability | Arduino-ESP32 | ESP-IDF |
|---|---|---|
| Native FreeRTOS task pinning | wrapped, limited | direct |
| `dac_continuous` DMA | not exposed | full API |
| `esp_dsp` optimized FFT | available but awkward to link | first-class |
| Memory caps for DMA / IRAM | hidden | explicit |
| ISR-in-IRAM control | difficult | trivial |
| sdkconfig tunables | hidden | full |

For a national-finals defense and a path to production, ESP-IDF is the right call.

## 9. Build & flash

```bash
# One-time
. $IDF_PATH/export.sh
cd firmware
idf.py set-target esp32s3

# Build, flash, monitor
idf.py build
idf.py -p COMx flash monitor
```

The first build pulls `esp_dsp` from the IDF managed-component registry.

## 10. What's deliberately out of scope (and why)

| Feature | Why deferred |
|---|---|
| BLE output to companion app | UART log proves the pipeline end-to-end; BLE is a clean follow-up. |
| Full IIS3DWB register map | Only the subset we use (CTRL1_XL, CTRL3_C, INT1_CTRL, OUTZ_*) is implemented — datasheet-driven minimalism. |
| Live calibration UI | Per-patient `f_healthy` override planned via NVS, simple write-tool. |
| Power management (deep sleep between scans) | The 4 s scan cycle is short; deep sleep adds latency, defer to v2. |

## 11. Risks & open items

- ODR bitfield value (`RS_CTRL1_ODR_2667HZ`) in `config.h` is set to a placeholder per IIS3DWB datasheet rev 4 — must be verified against the silicon rev shipped in the actual production batch.
- `dac_continuous_write_asynchronously` is the v5.1+ API; if targeting v5.0 use `dac_continuous_write` plus a TX-done callback chained to re-queue.
- For >50 hours continuous operation, periodic `spi_bus_get_attr` health-check + re-init would be added.
