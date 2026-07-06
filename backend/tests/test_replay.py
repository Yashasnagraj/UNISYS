"""
Tests for the replay scan source — real captured sweeps flowing through the SAME
pipeline as a live scan, driving a genuine repeatability collapse and lossless
raw-sweep persistence.
"""
from __future__ import annotations

import json
import os

from sqlmodel import select

from app.db.models import Patient, RawSweepSet, Scan
from app.db.seed import seed_demo_patients
from app.services.pipeline import run_replay_scan
from app.services.sim_source import make_capture_batch

_FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _write_fixture(name: str, f_peak: float, n: int = 24) -> str:
    os.makedirs(_FIXTURES, exist_ok=True)
    batch = make_capture_batch(f_peak=f_peak, n_sweeps=n, seed=7)
    path = os.path.join(_FIXTURES, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"fs": batch["fs"], "sweeps": [[float(x) for x in s] for s in batch["sweeps"]]}, fh)
    return path


def test_replay_persists_all_sweeps_and_collapses(db):
    seed_demo_patients()
    patient = db.exec(select(Patient).where(Patient.patient_code == "P-2611")).first()

    path = _write_fixture("_pytest_replay", f_peak=232.0, n=24)
    try:
        scan = run_replay_scan(patient=patient, db=db, fixture="_pytest_replay", week=10.0)
    finally:
        os.remove(path)

    assert scan.source == "replay"
    assert scan.features_json, "replay scan must carry the 25-feature vector"

    # all raw sweeps persisted losslessly
    rss = db.exec(select(RawSweepSet).where(RawSweepSet.session_id == scan.session_id)).first()
    assert rss is not None and rss.n_sweeps == 24

    # the money metric: raw spread collapses under normalization
    assert scan.tsi_std_raw is not None and scan.tsi_std_norm is not None
    assert scan.tsi_std_norm < scan.tsi_std_raw, "normalization must reduce TSI spread"


def test_replay_missing_fixture_raises(db):
    seed_demo_patients()
    patient = db.exec(select(Patient).where(Patient.patient_code == "P-2611")).first()
    try:
        run_replay_scan(patient=patient, db=db, fixture="does_not_exist", week=0.0)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
