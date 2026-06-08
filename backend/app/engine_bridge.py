"""
The ONE place that wires the validated ortho_simulator engine into the backend.

ortho_simulator/ is NOT an installable package — its modules import each other
as top-level (`from engine.x import ...`). So we put ortho_simulator/ on sys.path
and import the same way. Never `import ortho_simulator.engine` — it will fail.

Every other backend module imports the engine from HERE, so the wiring lives in
exactly one file.
"""
from __future__ import annotations

import os
import sys
import warnings

# scikit-learn version drift (model.pkl trained on 1.3, runtime is newer) emits
# benign InconsistentVersionWarning on unpickle — silence it, the model loads fine.
warnings.filterwarnings("ignore", message=".*InconsistentVersionWarning.*")
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

_ORTHO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "ortho_simulator")
)
if not os.path.isdir(_ORTHO):  # pragma: no cover - defensive
    raise RuntimeError(f"ortho_simulator engine not found at {_ORTHO}")
if _ORTHO not in sys.path:
    sys.path.insert(0, _ORTHO)

ORTHO_ROOT = _ORTHO

# --- Re-export the validated engine API (single import surface) --------------
from engine.signal_generator import (  # noqa: E402
    generate_scan_signal,
    generate_healthy_reference,
    add_gaussian_noise,
    FS,
)
from engine.fft_engine import (  # noqa: E402
    compute_psd,
    detect_peaks,
    compute_half_power_bandwidth,
    compute_spectrogram,
)
from engine.classification import predict_healing_status  # noqa: E402
from engine.clinical_metrics import (  # noqa: E402
    classify_healing,
    compute_rust,
    compute_rust_cortex_scores,
)
from engine.healing_prediction import predict as predict_healing  # noqa: E402
from ml.feature_extractor import extract_features, FEATURE_NAMES  # noqa: E402
from ml.generate_dataset import LABEL_NAMES  # noqa: E402
from data.bone_profiles import BONE_PROFILES  # noqa: E402
from data.demo_patients import DEMO_PATIENTS  # noqa: E402


def engine_health() -> dict:
    """Quick self-check used by GET /health."""
    ok = True
    detail = {}
    try:
        import numpy as np

        sig = generate_scan_signal(
            callus_pct=60.0, f_healthy=850.0, implant_loose=False,
            pressure_n=3.5, noise_level=0.01,
        )
        res = predict_healing_status(
            signal=sig["response"], fs=FS, f_healthy=850.0, callus_pct=60.0
        )
        detail["model_label"] = res.get("predicted_label")
        detail["n_features"] = len(FEATURE_NAMES)
        detail["labels"] = list(LABEL_NAMES)
        model_loaded = res.get("model_name", "").lower().startswith("random") or bool(
            res.get("probabilities")
        )
    except Exception as exc:  # pragma: no cover
        ok = False
        model_loaded = False
        detail["error"] = repr(exc)
    return {"engine_ok": ok, "model_loaded": model_loaded, **detail}


__all__ = [
    "ORTHO_ROOT",
    "generate_scan_signal",
    "generate_healthy_reference",
    "add_gaussian_noise",
    "FS",
    "compute_psd",
    "detect_peaks",
    "compute_half_power_bandwidth",
    "compute_spectrogram",
    "predict_healing_status",
    "classify_healing",
    "compute_rust",
    "compute_rust_cortex_scores",
    "predict_healing",
    "extract_features",
    "FEATURE_NAMES",
    "LABEL_NAMES",
    "BONE_PROFILES",
    "DEMO_PATIENTS",
    "engine_health",
]
