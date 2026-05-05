"""
ResoScan ML Classification — Random Forest prediction + rule-based fallback.

Loads the trained model and predicts healing status from spectral features.
Falls back to rule-based classification if model is unavailable.
"""

import os
import pickle
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model.pkl")
LABELS = ["Stable", "Delayed Union", "Non-Union", "Implant Failure"]

_model_cache = None


def _load_model():
    """Load the trained model from disk (cached)."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            _model_cache = pickle.load(f)
        return _model_cache
    return None


def _train_model_if_missing():
    """Train the model on first use if model.pkl doesn't exist."""
    if not os.path.exists(MODEL_PATH):
        from ml.train_model import train_and_save
        train_and_save()


def predict_healing_status(f_n: float, zeta: float, q_factor: float,
                           tsi: float, spectral_bandwidth: float,
                           peak_splitting: bool) -> dict:
    """Predict healing classification using trained Random Forest.

    Features: [f_n, zeta, q_factor, tsi, spectral_bandwidth, peak_splitting_flag]

    Returns:
        dict with predicted_label, confidence, probabilities
    """
    _train_model_if_missing()

    model_data = _load_model()
    features = np.array([[f_n, zeta, q_factor, tsi, spectral_bandwidth,
                          int(peak_splitting)]])

    if model_data is not None:
        clf = model_data["model"]
        proba = clf.predict_proba(features)[0]
        pred_idx = np.argmax(proba)
        pred_label = LABELS[pred_idx]
        confidence = float(proba[pred_idx]) * 100.0

        return {
            "predicted_label": pred_label,
            "confidence": confidence,
            "probabilities": {LABELS[i]: float(proba[i] * 100) for i in range(len(LABELS))},
        }

    # Fallback: rule-based classification
    return _rule_based_classification(f_n, zeta, tsi, peak_splitting)


def _rule_based_classification(f_n: float, zeta: float, tsi: float,
                               peak_splitting: bool) -> dict:
    """Rule-based fallback classification when ML model is unavailable."""
    if peak_splitting:
        return {
            "predicted_label": "Implant Failure",
            "confidence": 85.0,
            "probabilities": {"Stable": 5, "Delayed Union": 5,
                              "Non-Union": 5, "Implant Failure": 85},
        }
    if tsi > 75 and zeta < 0.04:
        return {
            "predicted_label": "Stable",
            "confidence": 90.0,
            "probabilities": {"Stable": 90, "Delayed Union": 8,
                              "Non-Union": 1, "Implant Failure": 1},
        }
    if tsi > 45:
        return {
            "predicted_label": "Delayed Union",
            "confidence": 72.0,
            "probabilities": {"Stable": 15, "Delayed Union": 72,
                              "Non-Union": 10, "Implant Failure": 3},
        }
    return {
        "predicted_label": "Non-Union",
        "confidence": 78.0,
        "probabilities": {"Stable": 5, "Delayed Union": 12,
                          "Non-Union": 78, "Implant Failure": 5},
    }
