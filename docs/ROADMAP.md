# ResoScan — Technical Roadmap (the closing slide)

What we built for the finals is a working end-to-end slice of the full system. This is where it goes
next — each item honestly labelled as *not yet built*, and gated behind the right rigor.

## Built now (demo-able, local, honest)
- **Deterministic physics engine** → f_peak, Q, damping, TSI (never learns).
- **Real captured sweeps** replayed through one pipeline → genuine repeatability collapse.
- **Knowledge graph + causal explanation** → similar prior cases, cited risk factors.
- **Human-in-the-loop** → clinician confirm/override → approved-only training data.
- **Champion/challenger continual retrain** → real frozen-holdout promotion gate, live model swap.

## Next (post-finals, in order)

1. **Real data first.** Capture 50+ repeat scans per limb + contralateral baselines; store every raw
   waveform. No model claim is real until this exists. *(Nothing below should ship before this.)*
2. **Learn from the raw signal.** A 1D-CNN / spectrogram model on the normalized waveform (learned
   features vs hand-crafted), with signal augmentation (SpecAugment, additive noise). Keep gradient
   boosting as the tabular baseline — it wins at small data scale (Grinsztajn 2022).
3. **Graph neural network** over the accumulated knowledge graph (GraphSAGE / GAT, PyTorch Geometric)
   — only once there are 100+ outcome-labelled cases. A GNN on three scans is premature.
4. **Causal counterfactuals.** Upgrade the hand-coded DAG to real do-calculus (DoWhy / EconML):
   *"if this patient stopped smoking, projected clearance shifts by X."*
5. **Azure deployment.** FastAPI + managed Postgres (relational + graph) + Blob (raw sweeps + model
   artifacts) on Azure Container Apps; scheduled retrain as an Azure ML job; MLflow model registry.
6. **Continual-learning governance.** Drift monitoring, replay buffer against catastrophic forgetting,
   shadow/canary promotion.

## The regulatory frame (this is what makes "improves day by day" responsible)

A continually-learning diagnostic is **Software as a Medical Device (SaMD)**. The FDA's
**Predetermined Change Control Plan (PCCP)** is the exact framework for AI that keeps learning after
deployment: you pre-specify what may change, how it's validated, and the rollback criteria. Our
champion/challenger frozen-holdout gate + version audit trail is the engineering substrate for a PCCP.
That is the difference between "the model retrains itself" (reckless) and "the model improves under a
pre-agreed control plan" (deployable).
