"""
Tests for the knowledge graph + causal explanation: cross-patient similar-case
retrieval (preferring confirmed outcomes), the causal narrative's active factors,
and the patient ego-graph shape.
"""
from __future__ import annotations

from sqlmodel import select

from app.db.models import Patient, Scan
from app.db.seed import backfill_demo_features, seed_demo_patients
from app.services import causal, knowledge_graph as kg


def _latest_feature_scan(db, code: str) -> Scan:
    p = db.exec(select(Patient).where(Patient.patient_code == code)).first()
    scans = [s for s in db.exec(select(Scan)) if s.features_json and s.patient_id == p.id]
    return scans[-1]


def test_similar_cases_are_cross_patient_and_prefer_outcomes(db):
    seed_demo_patients()
    backfill_demo_features()
    scan = _latest_feature_scan(db, "P-2611")

    cases = kg.similar_scans(db, scan, k=5)
    assert cases, "expected similar prior cases from the cohort"
    # never returns the query patient's own scans
    assert all(c["patient_id"] != scan.patient_id for c in cases)
    # confirmed-outcome cases are ranked ahead of unconfirmed ones
    has_outcome_flags = [c["has_outcome"] for c in cases]
    assert has_outcome_flags == sorted(has_outcome_flags, reverse=True)


def test_causal_explanation_lists_active_factors(db):
    seed_demo_patients()
    backfill_demo_features()
    # Vikram: smoker + diabetic + comminuted + low TSI late — several factors fire
    scan = _latest_feature_scan(db, "P-2810")
    patient = db.exec(select(Patient).where(Patient.patient_code == "P-2810")).first()

    exp = causal.explain_verdict(patient, scan, n_similar=3)
    factors = {f["factor"] for f in exp["active_factors"]}
    assert "smoker" in factors and "comminuted" in factors
    assert "matching 3 similar" in exp["narrative"]
    # each active factor carries a citation
    assert all(f["citation"] for f in exp["active_factors"])


def test_patient_ego_graph_shape(db):
    seed_demo_patients()
    backfill_demo_features()
    patient = db.exec(select(Patient).where(Patient.patient_code == "P-2611")).first()
    ego = kg.patient_ego_graph(db, patient.id)

    types = {n["type"] for n in ego["nodes"]}
    assert {"patient", "scan", "outcome"}.issubset(types)
    # similar_to edges connect this patient's scan to other-patient scans
    assert any(e["type"] == "similar_to" for e in ego["edges"])
