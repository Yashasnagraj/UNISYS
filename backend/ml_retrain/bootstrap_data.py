"""
Synthetic bootstrap corpus for the single-scan classifier.

Reuses the validated per-sample generator (`ml.generate_dataset._sample_one`) via
the engine bridge, so the 25 features and 4 labels are IDENTICAL to what the live
feature extractor produces — zero train/serve skew. Every row is synthetic and
tagged as such; the honest accuracy comes only when real clinician-confirmed
pairs are folded in on top (see services/feedback.collect_training_pairs).
"""
from __future__ import annotations

import numpy as np

import app.engine_bridge  # noqa: F401  — puts ortho_simulator on sys.path
from ml.generate_dataset import _sample_one  # noqa: E402
from app.engine_bridge import FEATURE_NAMES, LABEL_NAMES


def bootstrap_dataset(n_samples: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, y) of `n_samples` synthetic 25-feature rows with integer labels
    in [0, len(LABEL_NAMES)). Deterministic for a given seed."""
    rng = np.random.RandomState(seed)
    X = np.empty((n_samples, len(FEATURE_NAMES)), dtype=float)
    y = np.empty(n_samples, dtype=int)
    for i in range(n_samples):
        row = _sample_one(rng)
        X[i] = [row[name] for name in FEATURE_NAMES]
        y[i] = int(row["label"])
    return X, y


def n_labels() -> int:
    return len(LABEL_NAMES)
