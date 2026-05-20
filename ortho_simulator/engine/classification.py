"""
ResoScan ML Classification — bundled Random Forest on 25 engineered features.

Loads the model bundle saved by ml/train_model.py and predicts healing status
from the SAME feature extractor used during training (ml/feature_extractor.py),
guaranteeing identical feature schemas at train and inference time.

Single source of truth:
    - FEATURE_NAMES comes from ml/feature_extractor.py
    - LABEL_NAMES   comes from ml/generate_dataset.py
    - Both are stored inside model.pkl alongside the estimator and verified
      on load.
"""

import os
import pickle
import numpy as np

# Local imports (engine/ -> ml/)
from ml.feature_extractor import extract_features, FEATURE_NAMES
from ml.generate_dataset import LABEL_NAMES


MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model.pkl")

_model_cache = None


def _load_model():
    """Load and validate the bundled model. Cached after first call."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if not os.path.exists(MODEL_PATH):
        return None

    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)

    # Validate that feature_names and labels in the bundle match what we
    # import here. If they don't, predict() will raise ValueError at runtime,
    # which is far worse than failing fast at load.
    bundled_feats = list(bundle.get("feature_names", []))
    bundled_labels = list(bundle.get("labels", []))
    if bundled_feats != FEATURE_NAMES:
        raise RuntimeError(
            "Model feature schema drift: bundle has "
            f"{bundled_feats}\nbut feature_extractor exports {FEATURE_NAMES}. "
            "Retrain with ml/train_model.py."
        )
    if bundled_labels != LABEL_NAMES:
        raise RuntimeError(
            "Model label schema drift: bundle has "
            f"{bundled_labels} but generate_dataset exports {LABEL_NAMES}."
        )

    _model_cache = bundle
    return _model_cache


def predict_healing_status(signal: np.ndarray, fs: int, f_healthy: float,
                           callus_pct: float) -> dict:
    """Predict healing classification from a raw scan signal.

    Args:
        signal:     time-domain response from generate_scan_signal
        fs:         sampling rate (Hz)
        f_healthy:  patient/bone healthy reference frequency
        callus_pct: estimated callus stiffness percentage (for the
                    callus_proxy feature; can be 0 if unknown)

    Returns:
        dict with predicted_label, confidence, probabilities, top_features,
        and the full feature vector for downstream display.
    """
    feats = extract_features(signal=signal, fs=fs,
                             f_healthy=f_healthy, callus_pct=callus_pct)

    x = np.array([[feats[name] for name in FEATURE_NAMES]], dtype=float)

    bundle = _load_model()
    if bundle is not None:
        clf = bundle["model"]
        proba = clf.predict_proba(x)[0]
        idx = int(np.argmax(proba))
        pred_label = LABEL_NAMES[idx]
        confidence = float(proba[idx]) * 100.0

        # Top-3 contributing features by importance
        top_features = []
        if hasattr(clf, "feature_importances_"):
            order = np.argsort(clf.feature_importances_)[::-1][:3]
            top_features = [
                {"name": FEATURE_NAMES[i],
                 "value": float(x[0, i]),
                 "importance": float(clf.feature_importances_[i])}
                for i in order
            ]

        return {
            "predicted_label": pred_label,
            "confidence": confidence,
            "probabilities": {
                LABEL_NAMES[i]: float(proba[i] * 100) for i in range(len(LABEL_NAMES))
            },
            "top_features": top_features,
            "features": feats,
            "model_name": bundle.get("model_name", "unknown"),
        }

    # Fallback: rule-based classification on the extracted features
    return _rule_based_fallback(feats)


def _rule_based_fallback(feats: dict) -> dict:
    """Used only if model.pkl is missing (e.g. fresh checkout pre-training)."""
    tsi = feats["tsi"]
    zeta = feats["damping_ratio"]
    peak_split = feats["peak_splitting_flag"]

    if peak_split > 0.5:
        return {
            "predicted_label": "Implant Failure",
            "confidence": 85.0,
            "probabilities": {"Stable": 5, "Delayed Union": 5,
                              "Non-Union": 5, "Implant Failure": 85},
            "top_features": [],
            "features": feats,
            "model_name": "rule-based-fallback",
        }
    if tsi > 75 and zeta < 0.04:
        return {
            "predicted_label": "Stable",
            "confidence": 90.0,
            "probabilities": {"Stable": 90, "Delayed Union": 8,
                              "Non-Union": 1, "Implant Failure": 1},
            "top_features": [],
            "features": feats,
            "model_name": "rule-based-fallback",
        }
    if tsi > 45:
        return {
            "predicted_label": "Delayed Union",
            "confidence": 72.0,
            "probabilities": {"Stable": 15, "Delayed Union": 72,
                              "Non-Union": 10, "Implant Failure": 3},
            "top_features": [],
            "features": feats,
            "model_name": "rule-based-fallback",
        }
    return {
        "predicted_label": "Non-Union",
        "confidence": 78.0,
        "probabilities": {"Stable": 5, "Delayed Union": 12,
                          "Non-Union": 78, "Implant Failure": 5},
        "top_features": [],
        "features": feats,
        "model_name": "rule-based-fallback",
    }
