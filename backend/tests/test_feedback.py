"""
Tests for the human-in-the-loop feedback service: label validation, recording
confirm/override + outcomes, and assembling the retrain corpus from confirmed
labels only.
"""
from __future__ import annotations

import pytest
from sqlmodel import select

from app.db.models import Patient
from app.db.seed import backfill_demo_features, seed_demo_patients
from app.engine_bridge import FEATURE_NAMES, LABEL_NAMES
from app.services import feedback


def test_validate_label_rejects_unknown():
    with pytest.raises(ValueError):
        feedback.validate_label("Totally Bogus")
    for label in LABEL_NAMES:
        feedback.validate_label(label)   # no raise


def test_backfill_produces_confirmed_training_pairs(db):
    seed_demo_patients()
    n = backfill_demo_features()
    assert n > 0

    X, y = feedback.collect_training_pairs(db)
    assert X.shape[0] >= 3, "each backfilled patient should contribute a confirmed pair"
    assert X.shape[1] == len(FEATURE_NAMES)
    assert set(y.tolist()).issubset(set(range(len(LABEL_NAMES))))


def test_override_becomes_training_label(db):
    seed_demo_patients()
    backfill_demo_features()
    patient = db.exec(select(Patient).where(Patient.patient_code == "P-2611")).first()
    # a feature-bearing scan without a prior outcome
    from app.db.models import Outcome, Scan
    outcome_scan_ids = {o.scan_id for o in db.exec(select(Outcome))}
    scan = next(s for s in db.exec(select(Scan))
                if s.features_json and s.patient_id == patient.id and s.id not in outcome_scan_ids)

    feedback.record_feedback(db, scan_id=scan.id, agree=False,
                             override_label="Non-Union", clinician=None, notes="softer than scored")
    X, y = feedback.collect_training_pairs(db)
    # the override label must appear as a target
    assert LABEL_NAMES.index("Non-Union") in y.tolist()
