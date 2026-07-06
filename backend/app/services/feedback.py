"""
Human-in-the-loop feedback service.

Records clinician confirm/override on a scan verdict and ground-truth outcomes,
and assembles the retrain corpus of (25-feature vector, label) pairs from the
confirmed labels. Only clinician-approved data enters training — a bad scan
never silently retrains the model.
"""
from __future__ import annotations

import json

import numpy as np
from sqlmodel import Session, select

from app.db.models import ClinicianFeedback, Outcome, Scan
from app.engine_bridge import FEATURE_NAMES, LABEL_NAMES

_LABEL_INDEX = {name: i for i, name in enumerate(LABEL_NAMES)}


def validate_label(label: str) -> None:
    """Raise ValueError if `label` is not one of the four canonical LABEL_NAMES.
    The single-scan model bundle is locked to this label set, so a stray label
    would poison the retrain corpus and refuse to load."""
    if label not in _LABEL_INDEX:
        raise ValueError(f"label must be one of {LABEL_NAMES}, got '{label}'")


def record_feedback(db: Session, scan_id: int, agree: bool,
                    override_label: str | None, clinician: str | None,
                    notes: str | None) -> ClinicianFeedback:
    if override_label:
        validate_label(override_label)
    fb = ClinicianFeedback(
        scan_id=scan_id, agree=agree, override_label=override_label,
        clinician=clinician, notes=notes,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def record_outcome(db: Session, patient_id: int, scan_id: int | None,
                   true_label: str, weeks_to_walk: float | None,
                   rust_16w: int | None, source: str = "clinician") -> Outcome:
    validate_label(true_label)
    outcome = Outcome(
        patient_id=patient_id, scan_id=scan_id, true_label=true_label,
        weeks_to_walk=weeks_to_walk, rust_16w=rust_16w, source=source,
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


def _features_vector(scan: Scan) -> np.ndarray | None:
    if not scan.features_json:
        return None
    try:
        feats = json.loads(scan.features_json)
    except (json.JSONDecodeError, TypeError):
        return None
    try:
        return np.array([float(feats[name]) for name in FEATURE_NAMES], dtype=float)
    except (KeyError, TypeError, ValueError):
        return None


def collect_training_pairs(db: Session) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) from clinician-confirmed labels for retraining the single-scan
    classifier. Sources, in priority order per scan:

      1. a confirmed Outcome tied to the scan (ground truth), else
      2. a clinician override_label (disagreed with the ML verdict).

    Feature vectors are ordered by FEATURE_NAMES so they drop straight into the
    25-feature model. Returns empty arrays if there is nothing confirmed yet.
    """
    label_by_scan: dict[int, str] = {}

    # overrides first (lower priority), then outcomes overwrite (higher priority)
    for fb in db.exec(select(ClinicianFeedback)):
        if fb.override_label and fb.scan_id is not None:
            label_by_scan[fb.scan_id] = fb.override_label
    for o in db.exec(select(Outcome)):
        if o.scan_id is not None:
            label_by_scan[o.scan_id] = o.true_label

    X: list[np.ndarray] = []
    y: list[int] = []
    for scan_id, label in label_by_scan.items():
        if label not in _LABEL_INDEX:
            continue
        scan = db.get(Scan, scan_id)
        if not scan:
            continue
        vec = _features_vector(scan)
        if vec is None:
            continue
        X.append(vec)
        y.append(_LABEL_INDEX[label])

    if not X:
        return np.empty((0, len(FEATURE_NAMES))), np.empty((0,), dtype=int)
    return np.vstack(X), np.array(y, dtype=int)
