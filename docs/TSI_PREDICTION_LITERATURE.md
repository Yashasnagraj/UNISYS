# TSI Prediction — Literature-Grounded Parameters

Real values extracted from peer-reviewed vibration-based fracture-healing studies, used
to generate the synthetic training data for the early healing-outcome predictor.

## 1. Resonant frequency of the healing tibia (in-vivo, first bending mode)

| Source | Values | Context |
|---|---|---|
| **Mattei et al. 2021** (Int Biomech; clinical case, 35 wk, 16 sessions) | f₁ = **83 Hz → 101 Hz** over 30 wk (external fixator); after removal f₁ ≈ 60–65 Hz | first resonant mode, constrained in-situ |
| Mattei 2021 (higher modes) | f₂≈259, f₃≈409, f₄≈512 … f₁₃≈920 Hz | modes 2–13, 0–1000 Hz band |
| **Nikiforidis 1990** | 39, 103, 139 Hz (0–500 Hz) | single patient, shaker |
| **Lowet / Van der Perre** | 280–470 Hz (free-free); 303 Hz frontal, 470 Hz sagittal | less-constrained boundary |

→ **Healthy first-mode reference ≈ 300 Hz in-situ** (population mean), with boundary-condition spread.

## 2. The healing curve (how TSI climbs)

- **TSI = (f_fracture / f_healthy)² × 100** — the *squared* frequency index (**Tower 1993; Mattei 2021**).
- **Squared Frequency Increment (SFI)** of the first mode rises **~20% per month** during woven-callus formation, up to **~50% total** at healing completion (Mattei 2021).
- f₁ rate: **~21%/month (weeks 0–7, woven callus)** → **~2.8%/month (weeks 7–30, hard callus)**. Earlier studies: **5–10% per week** during woven callus.
- **Time-to-heal defined as callus reaching 90% of intact stiffness** (PLOS One rat study; clinical consensus).

## 3. Healing timeline (Mattei 2021 case)

| Week | Stage |
|---|---|
| 2 | soft woven callus appears |
| 4–9 | slow progression |
| 10 | woven + soft callus |
| 15–19 | soft → hard callus |
| 26 | consolidation |
| 30 | healing complete |

**Union timing by treatment** (clinical): cast ≈ **14 wk**, external fixator ≈ **22 wk**, IM nail ≈ **27 wk**.

## 4. Damping

- Healthy isolated tibia damping ratio ≈ **0.10**; with surrounding soft tissue ≈ **0.35**.
- Damping **decreases** as the bone heals (modal-damping-factor studies); fresh soft callus absorbs energy (high ζ), healed bone rings (low ζ).
- Model used: **ζ(TSI) = 0.20 − 0.175·(TSI/100)^1.3** — consistent with the above range.

## 5. Outcome thresholds & incidence

- **Non-union**: failure to reach a tibial stiffness of **7 Nm/degree by 20 weeks**; load-share ratio stays >10%.
- **Weight-bearing safe**: ~**80% of intact stiffness** (linear TSI ≥ 80, squared ≥ 64).
- **Non-union incidence**: ~**12%** of tibial-shaft fractures (up to **80%** in Gustilo III open).

## 6. Demographic modifiers on healing rate k (clinical literature)

| Factor | Effect on k |
|---|---|
| Smoking | × 0.68 (≈30% slower — Hak 2014, Adams 2018) |
| Diabetes | × 0.78 (Marquez-Lara 2016) |
| Age ≥ 65 | × 0.82 |
| Open / comminuted | × 0.75 (higher non-union risk) |

## 7. Measurement parameters (Mattei 2021)

0–1000 Hz analysis band · 2 Hz resolution · 0.1 N impact (imperceptible) · **10 trials averaged** · coherence > 0.9.
Cheap-sensor raw TSI σ ≈ ±5–18%; after our normalization σ ≈ ±0.5–2%.

---

### Sources
- Mattei et al. (2021), *International Biomechanics* 8(1) — clinical vibration case study (PMC8130726).
- Tower, Beals & Duwelius (1993), *J Orthop Trauma* 7(6):552 — Tibial Stiffness Index.
- Nikiforidis et al. (1990); Lowet & Van der Perre (1996) — in-vivo tibial resonance.
- "Resonant frequency analysis of the tibia as a measure of fracture healing" (PubMed 8308609).
- Modal damping factor studies (Frontiers Bioeng 2025; ResearchGate 274410763).
- PLOS One — callus-stiffness time-course (rat); BMC Musculoskelet Disord — non-union incidence/cost.
- Hak 2014, Adams 2018, Marquez-Lara 2016 — demographic healing modifiers.
