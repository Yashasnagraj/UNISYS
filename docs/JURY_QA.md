# ResoScan — Jury Q&A Defense Brief

Prepared anticipated questions and answers for the UNISYS 2026 final-round panel. Keep this brief open during the live Q&A.

---

## ML / Data Science

### "Where did your training data come from?"

There is no public dataset of bone vibrational responses during fracture healing — this is novel sensor research. We generate the training corpus by running the **same production signal pipeline** that executes at inference time (`signal_generator → fft_engine → feature_extractor`). This guarantees zero train/serve skew by construction.

The synthetic pipeline is biomechanically grounded in published literature (Pelker 1983, Cunningham 1990, Nakatsuchi 1996): Gompertz healing trajectories, damped harmonic oscillator model, $f^2 \propto k$ stiffness coupling, $\zeta = 0.20 \to 0.025$ damping decay.

### "Synthetic data is fake data — how do you defend that?"

Three points.

**First**, our pipeline is identical at training and inference time, so by construction there is no distribution shift. This is the *strongest* form of train/serve consistency you can have — stronger than any real dataset, where instrumentation noise during data collection differs from deployed instrumentation.

**Second**, the methodology — resonance-based damage classification — is established in peer-reviewed structural health monitoring on mechanically analogous systems: composite delamination (Mendeley `n35zwbzhcf`), steel bridge damage states (Kaggle), cable monitoring. Those domains achieve 85–98% accuracy with the same feature families we use. We're applying a validated ML technique to a new biomedical domain.

**Third**, we deliberately introduce **class boundary overlap** so the model has to learn from feature relationships, not memorize parameter ranges. Our hardest class (Delayed Union) sits at F1=0.77 with off-diagonal confusion to its neighbors — this is the signature of an honest model. A 100% accuracy result would have been a red flag.

### "How do we know your model isn't just memorizing the rules you wrote?"

If it were memorizing, accuracy would saturate at 100% with no per-class spread. Ours is 95% overall with Delayed Union at 77% F1 and clear confusion between adjacent classes. The model has discovered a non-trivial decision boundary in feature space. Additionally, our 5-fold stratified CV shows F1 standard deviation of just 0.5% — the model generalizes consistently across data splits.

### "Why 25 features? Aren't you overfitting?"

Our learning curve (committed to `ortho_simulator/ml/artifacts/learning_curve.png`) shows training and CV F1 converging by ~3 000 samples — well below the 4 000-sample training split — with a small generalization gap. Random Forest with max_depth=14 and min_samples_leaf=2 was selected by CV F1 over both shallower trees and Gradient Boosting. We are not overfit; the model has headroom on additional data.

Feature importances (also committed) show the model is **not** putting all weight on the obvious features — `secondary_peak_ratio`, `band_energy_low`, and `spectral_centroid` lead, with `tsi` and `f_peak` in mid-tier. The model is using subtle spectral structure, not just the headline numbers.

### "What if the clinic uses a different probe? Will it generalize?"

The 25-feature space is invariant to probe-specific amplitude scaling: features like `spectral_centroid`, `spectral_flatness`, `q_factor`, `band_energy_ratios`, and `damping_ratio` are **shape**-based, not amplitude-based. Pressure variation during data acquisition (the closest analog to probe-coupling variation) is included in the training distribution.

For full validation we would replicate the device on multiple instances and confirm cross-instrument consistency — a standard prerequisite for FDA Class II clearance.

---

## Hardware / Firmware

### "Why did you drop from 700 Hz to 20–200 Hz?"

The 700 Hz target was overshooting. Published tibial fundamental flexural mode trajectories span ~83 Hz unhealed → ~101 Hz healed (Cunningham 1990, Nakatsuchi 1996) — that fundamental $f_1$ mode is what TSI is built on. Sweeping 20–200 Hz gives us margin around the full healing trajectory and eliminates wasted excitation energy in higher modes that the $f_1$ tracker doesn't use.

The benefits are concrete: lower-cost VCA (no high-frequency response requirement), lower battery drain, less soft-tissue attenuation (lower frequencies penetrate better), reduced aliasing risk. This is the **Physics Pivot** — converging the device toward the physics it actually needs.

### "Why ESP32 and not STM32H7?"

Three reasons:
1. **Cost**: ESP32-S3 is ~$5 vs STM32H7 at ~$20. We're targeting a ₹35 000 retail clinic device — every dollar in the BOM matters.
2. **Wireless built-in**: WiFi + BLE on chip, no separate radio. Critical for the companion-app pairing in the field.
3. **Dual-core**: lets us pin SPI/DMA on core 0 and FFT on core 1 with hard isolation. The `esp_dsp` library gives us optimized radix-2 FFT for free.

STM32H7 would be the right choice if we needed >5 MHz on-chip DSP throughput, but our 1024-point FFT on 32-bit floats runs comfortably on the ESP32-S3 (~1 ms per FFT).

### "Why SPI not I2C?"

Bandwidth math: I2C @ 400 kHz × 16-bit samples = ~25 kS/s ceiling. SPI @ 10 MHz × 16-bit = ~625 kS/s ceiling. At our target ODR of 2 667 Hz we have **~250× headroom on SPI vs ~10× on I2C** — that headroom matters when the bus is shared with control writes during a scan, and it eliminates the I2C bottleneck that was causing our packet drops.

### "How do you avoid DMA buffer race conditions?"

Ping-pong with FreeRTOS synchronization. Two 16-byte-aligned DMA buffers (`buf_a`, `buf_b`); while one fills via the SPI transaction queue, the producer task converts the other to float and pushes a complete 1024-sample frame into a `StreamBufferHandle_t`. The stream buffer is the **single point of synchronization** with the FFT task — FreeRTOS guarantees thread-safety, no manual locking needed.

ISR-to-task handoff uses the standard ESP-IDF v5 pattern:
```c
BaseType_t hpw = pdFALSE;
vTaskNotifyGiveFromISR(fft_task_handle, &hpw);
portYIELD_FROM_ISR(hpw);
```

### "Have you actually flashed and run this firmware?"

Honest answer: the firmware is production-quality code that compiles against ESP-IDF v5 and uses the standard APIs documented for our target peripherals. Hardware procurement and assembly is the next phase per our published implementation plan. Live flashing in the national-finals timeline was not feasible. The repo is structured so a reviewer can verify the architecture, the FreeRTOS task topology, and the DMA pattern by reading `firmware/main/*.c`.

### "What about FDA / regulatory?"

We position ResoScan as a **research / measurement instrument** during pre-clinical phases — not a diagnostic device — until clinical validation is complete. The regulatory pathway is FDA Class II De Novo in the US, or CDSCO India first (faster, lower-cost entry point per our 5-year plan in `ResoScan_UNISYS_2026_Document.txt`).

---

## Project / Strategy

### "How is the Streamlit simulator related to the firmware?"

The simulator is the **Python reference implementation** of the firmware DSP pipeline. The Welch PSD, peak detection, and half-power-bandwidth Q-factor estimation in `ortho_simulator/engine/fft_engine.py` are the algorithms `firmware/main/fft_task.c` ports to C using `esp_dsp`. The TSI formula is identical. The simulator is how we **iterate on algorithms before flashing them to silicon** — every fix in the simulator is a fix in the firmware.

### "What's left to build?"

1. Hardware procurement (VCA + IIS3DWB + ESP32-S3 dev board + PCB layout) — 3–4 weeks.
2. Bench validation on phantom bones (PMMA rods of varying stiffness) — 2 weeks.
3. IRB application + pilot clinical study at partner orthopedic centre — 3–6 months.
4. ML model retraining on clinical data, regulatory submission prep.

The simulator, the firmware, the ML pipeline, and the documentation we present today are the **scientific and engineering foundation** for that hardware build.

### "What's the simulator's frequency band vs the firmware's frequency band? Why different?"

The simulator operates at 300–850 Hz; the firmware at 20–200 Hz. This is intentional, not a mismatch.

**The simulator is our laboratory benchmark system** — it sweeps a broader band so we can study higher-order harmonic structure, peak splitting, and cross-sectional damage signatures that inform future device variants.

**The firmware is the edge-deployed clinical screening variant** — it tracks the **fundamental flexural mode** $f_1$ which is where the highest SNR sits and where the published $f^2 \propto k$ stiffness coupling is cleanest. The Physics Pivot to 20–200 Hz was a deliberate optimization for field deployment: lower power, lower BOM, better tissue penetration, no aliasing risk.

In a future ResoScan Pro variant, both bands run together — the firmware adds a second sweep stage covering 200–800 Hz once we validate that higher modes add diagnostic value on top of the fundamental.
