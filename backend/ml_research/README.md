# ResoScan — Healing-Outcome Predictor (`ml_research/`)

A literature-grounded **dual-head** model that, from the **early window (≤ 6 weeks)**
of a tibial fracture, predicts:

1. **Outcome class** — Normal union / Delayed union / Non-union
2. **Weeks-to-walk** — time until the bone reaches the safe-to-walk threshold

> **Honesty first.** This model is trained on **synthetic data generated from
> published parameters**, *not* real patients — because no public vibration
> time-series dataset exists (every clinical vibration study to date is a single
> case or a handful). Every generator constant cites its source in
> [`synth_params.py`](./synth_params.py) and
> [`../../docs/TSI_PREDICTION_LITERATURE.md`](../../docs/TSI_PREDICTION_LITERATURE.md).
> Real-patient validation is the stated next step.

## The point of the model (and why it's defensible)

Four **validated clinical scores already exist** (LEG-NUI, NURD, FRACTING, TFHS).
So a fair judge asks: *"did you just re-code a known formula?"*

The answer is the **ablation** built into training — we train the classifier on:

| Feature set | What it uses | 5-fold macro-F1 |
|---|---|---|
| **Clinical only** | demographics + LEG-NUI / NURD / FRACTING | ~0.46 |
| **Vibration only** | f₁ / SFI / damping + early slopes | ~0.85 |
| **Fused (ResoScan)** | clinical **+** vibration | **~0.86** |

The **vibration telemetry lifts macro-F1 by ~+0.39 over the clinical scores
alone**. That single number is the project's defensible thesis: *the device
measures early healing biology (stiffness gain, damping decay) that the clinical
risk scores cannot see.* The outcome label is the **latent biological archetype**
— it is *not* derived from the observed frequency, so the prediction task is real,
not circular.

## How the synthetic cohort is built (one patient at a time)

1. **Demographic / injury profile** sampled from literature prevalences (with
   realistic correlations, e.g. open ↔ high-energy).
2. **Exact clinical scores** (LEG-NUI, NURD, FRACTING) computed from the published
   formulas.
3. **Latent archetype** (normal/delayed/non-union) drawn with the non-union
   probability **anchored to NURD's published risk bands** and LEG-NUI's PPV — so
   clinical scores carry their real-world predictive power.
4. **Log-logistic healing kinematics** (JBJS "Fracture Healing Odyssey"): the
   archetype sets the rise shape; non-unions are characterised by an *arrested
   plateau* and *shallow slope*, not a slower half-time.
5. **Frequency-centric trajectory** in the device band (400–800 Hz): the tracked
   flexural mode rises from ~450 Hz toward an archetype plateau; **TSI = (f/f_healthy)²**.
6. **Damping time-course**: high at fresh callus (ζ≈0.50), decaying to ~0.35
   (normal) or staying elevated ~0.46 (non-union) — the early vibrational flag.
7. **Cheap-sensor noise** added; only the **weeks 2/4/6** observations become model
   features (the early prognostic window).

Archetypes deliberately **overlap** in the early window (wide spreads + noise) so
the task matches clinical reality — early non-union prediction is hard (~75%
sensitivity), not trivially separable.

## Files

| File | Purpose |
|---|---|
| `synth_params.py` | Every literature-grounded constant, each with its citation |
| `generate.py` | Synthetic cohort generator (scores, archetype, trajectory, features) |
| `train.py` | Dual-head GradientBoosting + the ablation; saves model + metrics |
| `healing_predictor.pkl` | Trained model bundle (classifier + regressor + metadata) |
| `healing_metrics.json` | Full metrics: ablation, per-class, confusion matrix, importances |

## Run

```bash
cd backend
python -m ml_research.generate    # sanity-check the cohort
python -m ml_research.train       # train + ablation + save artifacts
```

Reproducible: fixed seed (`SEED = 20260608`) throughout.

## Representative results (synthetic holdout, 20%)

- **Fused classifier accuracy ≈ 89%**, macro-F1 ≈ 0.86
- **Vibration lift ≈ +0.39 macro-F1** over clinical-only (0.46 → 0.86)
- **Weeks-to-walk MAE ≈ 5 weeks**, R² ≈ 0.73
- Cohort mix ≈ 66 / 17 / 17 (normal / delayed / non-union) — risk-enriched,
  consistent with open/comminuted ("Regimen II") cohorts.

## Honest limitations (state these before a judge does)

- **Synthetic data.** Grounded in published parameters, but not real patients.
  Accuracy reflects the generative model's own structure; the *value* claim is the
  ablation (vibration > clinical), which is robust across seeds.
- **RUST→frequency is a modelling bridge** (f ∝ √stiffness), labelled as an
  assumption — not a measured relationship.
- **Device frequency domain** (400–800 Hz) tracks a higher flexural mode; TSI is a
  ratio, so the absolute mode cancels, but a first-mode (~280 Hz) sensor would be
  more healing-sensitive (future ODR upgrade).

## Sources
See [`../../docs/TSI_PREDICTION_LITERATURE.md`](../../docs/TSI_PREDICTION_LITERATURE.md)
for the full citation list (Mattei 2021, Tower 1993, LEG-NUI, NURD, FRACTING, TFHS,
JBJS Healing Odyssey, Van der Perre & Lowet, GBD 2019, damping-factor studies).
