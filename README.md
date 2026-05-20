# ResoScan — Resonant Modal Spectroscopy for Bone Fracture Healing

> *UNISYS 2026 National Finals project*

ResoScan is a low-cost, non-invasive, radiation-free diagnostic for monitoring fracture healing. Instead of imaging the bone, we *listen* to it: a controlled mechanical chirp excites the bone, a MEMS accelerometer captures the resonant response, and on-device DSP extracts a **Tibial Stiffness Index** that tracks healing weeks before X-ray can.

**Target BOM**: ₹6 000–8 000 (~$80). **Target retail**: ₹35 000 — vs the ₹15–35 lakh FibroScan that exists today.

---

## Live demo

**Primary — Next.js clinical product (recommended for judges):**

➡️ **Live**: https://web-bice-phi-71.vercel.app
➡️ **Source**: https://github.com/Yashasnagraj/resoscan

Premium medical-product UI built for the UNISYS finals. Three routes:

- `/` — landing page (hero, problem, how it works, team)
- `/dashboard/scan` — **live scan experience**, the centerpiece. Body silhouette with breathing tibia, animated Lorentzian frequency response, healing score, days-to-walk, confidence, recommendation.
- `/dashboard/patients` — three-patient triptych (Arjun cleared / Priya delayed / Vikram non-union risk) with full Gompertz trajectory chart.
- `/dashboard/model` — how accurate the AI is, in plain English. 95% accuracy, 25 measurements per scan, explainable AI.

**Fallback — Streamlit clinical simulator (technical depth):**

➡️ The Streamlit app at `ortho_simulator/app.py` remains live and serves as the engineering-deep backup. Configure via the deploy form at https://share.streamlit.io with repo `Yashasnagraj/UNISYS`, branch `main`, main file `ortho_simulator/app.py`.

---

## Repo layout

```
ResoScan/
├── ortho_simulator/        # Streamlit clinical UI + Python simulation engine
│   ├── app.py              #   main scan page
│   ├── pages/              #   Streamlit multipage entries
│   │   ├── 1_Model_Validation.py
│   │   └── 2_Patient_Tracking.py
│   ├── engine/             #   signal_generator, fft_engine, clinical_metrics, classification
│   ├── ui/                 #   charts, panels, PDF report
│   ├── data/               #   bone profiles, fracture profiles, training_dataset.csv
│   └── ml/                 #   feature_extractor, generate_dataset, train_model, artifacts/
├── firmware/               # ESP-IDF v5 firmware for the on-device DSP pipeline
│   ├── main/
│   │   ├── main.c
│   │   ├── config.h
│   │   ├── chirp_gen.c     #   DAC + DMA chirp 20-200 Hz
│   │   ├── sensor_spi.c    #   IIS3DWB SPI master + DMA ping-pong
│   │   ├── fft_task.c      #   esp_dsp FFT + peak detection
│   │   └── stiffness.c     #   TSI computation
│   ├── sdkconfig.defaults
│   └── README.md
└── docs/                   # Methodology, jury Q&A, firmware architecture
    ├── MODEL_VALIDATION.md
    ├── JURY_QA.md
    └── FIRMWARE_ARCHITECTURE.md
```

---

## How simulator and firmware connect

The simulator is the **Python reference implementation** of the firmware DSP pipeline. Both use:

- the same FFT method (Welch PSD in Python / `dsps_fft2r_fc32` in C)
- the same peak detection logic
- the same half-power-bandwidth Q-factor estimation
- the **same TSI formula** $\text{TSI} = (f_1 / f_\text{healthy})^2 \times 100$

They differ in scope, by design:

| | Simulator (`ortho_simulator/`) | Firmware (`firmware/`) |
|---|---|---|
| **Role** | Laboratory benchmark + algorithm dev | Edge-deployed clinical screening variant |
| **Frequency band** | 300–850 Hz (full spectral analysis, higher-order modes) | 20–200 Hz (fundamental flexural mode only) |
| **Why** | Studies the entire mechanical signature, informs future variants | Optimized for SNR, battery life, BOM, and tissue penetration in field deployment |
| **Implementation** | Python + NumPy + SciPy + scikit-learn | C + ESP-IDF v5 + esp_dsp + FreeRTOS |

Algorithm fixes flow simulator → firmware. ML model improvements flow simulator → firmware (parameters export). Validation flows back from clinical hardware → simulator once we have IRB approval and real patient data.

---

## Quick start

### Run the simulator locally

```bash
pip install -r requirements.txt
streamlit run ortho_simulator/app.py
```

### Regenerate ML dataset and retrain

```bash
python ortho_simulator/ml/generate_dataset.py    # ~13 s for 5 000 samples
python ortho_simulator/ml/train_model.py         # ~30 s, writes artifacts
```

### Build & flash firmware

```bash
. $IDF_PATH/export.sh
cd firmware
idf.py set-target esp32s3
idf.py build
idf.py -p COMx flash monitor
```

See [`firmware/README.md`](firmware/README.md) for hardware wiring and pinout.

---

## ML pipeline at a glance

- **25 engineered features** (12 spectral + 7 time-domain + 4 damping + 2 clinical)
- **5 000 synthetic samples** generated through the production pipeline (same path used at inference — zero train/serve skew)
- **Class boundary overlap deliberately introduced** so the model must learn rather than memorize
- **Random Forest** (n=200, max_depth=14, balanced class weights) selected by 5-fold stratified CV over Gradient Boosting
- **CV F1-macro 0.934 ± 0.005**, **holdout 95.3%**, **external validation 95.6%**
- Realistic per-class spread: Delayed Union (boundary class) at F1 0.77 — the signature of an honest model

Full methodology in [`docs/MODEL_VALIDATION.md`](docs/MODEL_VALIDATION.md).

---

## Firmware architecture at a glance

```
chirp_gen → VCA → bone → accelerometer → SPI@10MHz DMA ping-pong
                                                |
                                                v
                                         sensor_task (core 0)
                                                |
                                                v   FreeRTOS StreamBuffer
                                                |
                                                v
                                          fft_task (core 1, esp_dsp)
                                                |
                                                v
                                          stiffness (TSI → UART log)
```

Refactor highlights:

- **Physics Pivot**: chirp narrowed to 20–200 Hz for fundamental-mode tracking (Cunningham 1990, Nakatsuchi 1996).
- **SPI @ 10 MHz** replaces I2C @ 400 kHz — 25× the bus bandwidth ceiling, no more bottleneck.
- **DMA ping-pong** with 16-byte-aligned buffers — CPU never blocks on acquisition.
- **Dual-core pinning** — SPI/DMA on core 0, FFT/DSP on core 1, hard isolation.
- **`esp_dsp` optimized FFT** — 1024-point radix-2 in ~1 ms.

Full architecture in [`docs/FIRMWARE_ARCHITECTURE.md`](docs/FIRMWARE_ARCHITECTURE.md).

---

## Project status

| | Status |
|---|---|
| Streamlit simulator | ✅ deployed |
| ML pipeline (dataset + model + validation) | ✅ trained, 95% accuracy, artifacts in repo |
| ESP-IDF firmware (architecture + source) | ✅ production-quality code, ready for silicon |
| PCB design + procurement | ⏳ next phase |
| Bench validation on phantom bones | ⏳ next phase |
| IRB-approved clinical pilot | ⏳ Q3 2026 target |
| FDA Class II / CDSCO regulatory | ⏳ Q4 2026 target |

---

## Authors

Yashas N · Jeeth Kataria · Naveen Gopalakrishna Patil
Ramaiah Institute of Technology · UNISYS 2026

Project guide: Dr. Sowmya B. J.

See [`ResoScan_UNISYS_2026_Document.txt`](ResoScan_UNISYS_2026_Document.txt) for the full submission document.
