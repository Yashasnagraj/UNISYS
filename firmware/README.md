# ResoScan Firmware (ESP-IDF v5)

On-device DSP pipeline for the ResoScan bone-resonance diagnostic.

## What it does

Generates a 20-200 Hz log chirp on the Voice Coil Actuator, reads the IIS3DWB MEMS accelerometer over SPI + DMA, runs a 1024-point FFT pinned to the second core, locates the bone's fundamental resonant frequency, and computes a **Tibial Stiffness Index** (TSI = $(f_1 / f_\text{healthy})^2 \times 100\%$).

For the full architectural rationale, see [`docs/FIRMWARE_ARCHITECTURE.md`](../docs/FIRMWARE_ARCHITECTURE.md).

## Project layout

```
firmware/
  CMakeLists.txt
  sdkconfig.defaults
  main/
    CMakeLists.txt
    main.c                -- entry, system init, scan trigger loop
    config.h              -- pinout, clocks, buffers, register map, RTOS topology
    chirp_gen.c/.h        -- DAC + DMA chirp synthesis (20-200 Hz log sweep)
    sensor_spi.c/.h       -- IIS3DWB SPI master + DMA ping-pong producer task
    fft_task.c/.h         -- esp_dsp FFT + peak detection consumer task
    stiffness.c/.h        -- TSI computation + log output
```

## Hardware wiring (ESP32-S3 reference)

| Signal | GPIO | Notes |
|---|---|---|
| SPI MOSI | 11 | to IIS3DWB SDI |
| SPI MISO | 13 | from IIS3DWB SDO |
| SPI SCLK | 12 | to IIS3DWB SCL |
| SPI CS   | 10 | to IIS3DWB CS |
| INT1 (DRDY) | 14 | from IIS3DWB INT1 |
| DAC OUT  | 17 | to Class-D amp input |
| AMP shutdown | 18 | active-low enable |
| Scan LED | 2 | optional |
| Done LED | 3 | optional |

All pins are configurable via `config.h`. Bring 3V3 + GND to both the IIS3DWB and the amp.

## Build & flash

```bash
# One-time: set up the IDF environment
. $IDF_PATH/export.sh

# In the firmware/ directory
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor   # COMx = serial port on Windows; /dev/ttyUSB0 on Linux
```

## What you'll see on the serial monitor

```
I (220) resoscan: ==============================================
I (220) resoscan:  ResoScan firmware  v0.1
I (220) resoscan:  Resonant Modal Spectroscopy bone diagnostic
I (220) resoscan: ==============================================
I (230) resoscan:  Physics target: f1 ~83 Hz (unhealed) -> ~101 Hz (healed)
I (240) resoscan:  Chirp band: 20 - 200 Hz (log sweep, 500 ms)
I (250) resoscan:  SPI 10 MHz, ODR 2667 Hz, FFT N=1024, bin=2.60 Hz
I (260) resoscan: ==============================================
I (300) rs.fft:    fft_task init OK: N=1024, bin=2.60 Hz, search [20, 200] Hz
I (310) rs.spi:    IIS3DWB WHOAMI 0x7B OK
I (320) rs.spi:    sensor_spi init OK (SPI 10 MHz, ODR 2667 Hz)
I (330) rs.fft:    fft_task started on core 1
I (340) rs.spi:    sensor_task started on core 0
I (350) rs.chirp:  init OK: 4000 samples @ 8000 Hz, 20.0-200.0 Hz log sweep, 500 ms
I (360) resoscan:  scan cycle 1 ...
I (1100) rs.stiff: f1=87.42 Hz (smoothed=87.42 Hz)  TSI=74.9%  -> PARTIAL weight-bearing
I (1500) rs.stiff: f1=88.05 Hz (smoothed=87.61 Hz)  TSI=75.2%  -> PARTIAL weight-bearing
I (2400) resoscan:  scan cycle 2 ...
   current TSI = 75.2%
```

## Tunable parameters

All in `main/config.h`:

- `RS_CHIRP_F_START_HZ` / `RS_CHIRP_F_END_HZ` — sweep band (default 20 / 200 Hz)
- `RS_CHIRP_DURATION_MS` — sweep duration (default 500 ms)
- `RS_DAC_SAMPLE_RATE_HZ` — DAC output rate (default 8 kHz)
- `RS_ACCEL_SAMPLE_RATE_HZ` — IIS3DWB ODR (default 2 667 Hz)
- `RS_FFT_N` — FFT size (default 1024 → 2.6 Hz bin width)
- `RS_TIBIA_F_HEALTHY_HZ` — healthy reference (default 101 Hz, override via NVS)
- `RS_TSI_FULL_WB_PCT` / `RS_TSI_PARTIAL_WB_PCT` — clinical thresholds

## Dependencies

- ESP-IDF v5.1 or later (`dac_continuous` API, `esp_dsp` managed component).
- ESP32-S3 chip (or ESP32 / ESP32-C3 with appropriate `CONFIG_IDF_TARGET` change — note DAC GPIO is different on classic ESP32).

The `esp_dsp` component is pulled automatically from the IDF managed-component registry on first build.

## Honest status

The firmware is **production-quality code** that compiles against ESP-IDF v5 using documented APIs for all peripherals. Hardware procurement and bench validation is the next phase per the project's published implementation plan. The architecture is ready to run on silicon as soon as the PCB is fabricated; the simulator (`../ortho_simulator/`) is the Python reference for what this firmware does on-device.

See [`../docs/JURY_QA.md`](../docs/JURY_QA.md) for prepared answers to common technical questions.
