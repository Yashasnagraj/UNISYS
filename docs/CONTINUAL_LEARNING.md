# ResoScan — Continual Learning (Human-in-the-Loop)

How ResoScan improves "day by day" from real, clinician-confirmed data — safely.

## What learns, and what doesn't

ResoScan has **two** models, deliberately separated:

| Model | Features | Role | Continually retrained? |
|---|---|---|---|
| **Single-scan classifier** (`ortho_simulator/ml/model.pkl`) | 25 signal features from one scan | Reads a live scan → healing label | **Yes** — this is the learning loop |
| **Longitudinal prognostic** (`ml_research/healing_predictor.pkl`) | 22 features across weeks 2/4/6 | Early outcome + weeks-to-walk | **No** — frozen; it's the "Model" slide |

The **physics engine** (FFT → f_peak, Q, damping, TSI) is deterministic and never learns — it is the ground-truth layer.

## The loop

```
live scan ─► verdict ─► clinician confirms / overrides ─► confirmed (features, label)
                                                              │
             frozen holdout ◄── champion / challenger gate ◄──┘ + synthetic bootstrap
                                        │
                        promote iff challenger ≥ champion  ─► live model swap (no restart)
```

1. **Ingest** — a scan produces the 25-feature vector and an ML verdict (`POST /api/scans`).
2. **Human-in-the-loop** — `POST /api/scans/{id}/confirm` (agree / override) and
   `POST /api/scans/{id}/outcome` (ground-truth label). **Only approved data enters training** — a
   bad scan never silently retrains the model.
3. **Retrain** (`POST /api/model/retrain`) — a *challenger* is trained on the synthetic bootstrap
   **plus every confirmed pair** (`services/feedback.collect_training_pairs`), then scored against the
   current champion on an **identical frozen holdout** (`ml_retrain/frozen_holdout.npz`).
4. **Promote** — only if `challenger_f1 ≥ champion_f1`. On promotion the bundle is copied to the live
   model path and the in-process cache is dropped (`engine_bridge.reset_signal_model_cache`), so the
   next scan uses the new model with no server restart.
5. **Audit** — every version (F1, champion F1, clinician-pairs folded in, promoted/active) is recorded
   in `model_versions` and served by `GET /api/model/versions`.

## Honesty notes (state these on stage)

- **Champion v1 is deliberately trained on a smaller synthetic set**, so a challenger with more data +
  real confirmed cases can demonstrably beat it. The **gate is not rigged**: champion and challenger
  score on the *same* held-out set, and clinician pairs are **train-only** (no leakage).
- The bootstrap corpus is **synthetic** and labelled as such; the credible accuracy is what emerges once
  real confirmed outcomes accumulate.
- Single worker process assumed for the live cache swap.

## Roadmap

Scheduled/nightly retrain, drift monitoring, replay-buffer against catastrophic forgetting, and Azure
deployment — all under an **FDA Predetermined Change Control Plan (PCCP)**, the regulatory framework for
continually-learning medical AI. See `docs/ROADMAP.md`.
