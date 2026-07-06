"""
Tests for the champion/challenger continual retrain.

Both models are scored on the SAME frozen holdout, so promotion is honest. These
tests monkeypatch the model paths into a tmp dir so the committed model.pkl is
never touched, and cover both the promote (>=) and reject (<) branches of the
gate.
"""
from __future__ import annotations

import os
import shutil

import pytest
from sqlmodel import select

from app.db.models import ModelVersion
from app.db.seed import backfill_demo_features, seed_demo_patients
from app.engine_bridge import SIGNAL_MODEL_PATH as REAL_MODEL
import ml_retrain.retrain as R


@pytest.fixture()
def isolated_paths(tmp_path):
    """Redirect all retrain artifacts into a temp dir; restore afterwards."""
    saved = (R.SIGNAL_MODEL_PATH, R.BASELINE_BACKUP, R.VERSIONS_DIR,
             R.HOLDOUT_PATH, R.CHALLENGER_SYNTHETIC_N)
    R.SIGNAL_MODEL_PATH = str(tmp_path / "active.pkl")
    R.BASELINE_BACKUP = str(tmp_path / "baseline.pkl")
    R.VERSIONS_DIR = str(tmp_path / "versions")
    R.HOLDOUT_PATH = str(tmp_path / "holdout.npz")
    shutil.copyfile(REAL_MODEL, R.SIGNAL_MODEL_PATH)  # seed a live model to back up
    before = os.path.getmtime(REAL_MODEL)
    yield
    (R.SIGNAL_MODEL_PATH, R.BASELINE_BACKUP, R.VERSIONS_DIR,
     R.HOLDOUT_PATH, R.CHALLENGER_SYNTHETIC_N) = saved
    assert os.path.getmtime(REAL_MODEL) == before, "committed model.pkl must be untouched"


def test_establish_then_promote(db, isolated_paths):
    seed_demo_patients()
    backfill_demo_features()

    champ = R.establish_champion(db)
    assert champ is not None and champ.version == 1 and champ.is_active

    result = R.retrain_challenger(db)
    # larger synthetic corpus + real pairs -> ties/beats the under-trained champion
    assert result["promoted"] is True
    assert result["challenger_f1"] >= result["champion_f1"]
    assert result["clinician_pairs"] >= 3

    active = db.exec(select(ModelVersion).where(ModelVersion.is_active == True)).all()  # noqa: E712
    assert len(active) == 1 and active[0].version == 2


def test_challenger_can_be_rejected(db, isolated_paths):
    seed_demo_patients()
    backfill_demo_features()
    R.establish_champion(db)

    # cripple the challenger's corpus so it is worse than the champion
    R.CHALLENGER_SYNTHETIC_N = 30
    result = R.retrain_challenger(db)

    assert result["promoted"] is False
    assert result["challenger_f1"] < result["champion_f1"]
    # champion (v1) stays active; challenger recorded but not activated
    active = db.exec(select(ModelVersion).where(ModelVersion.is_active == True)).all()  # noqa: E712
    assert len(active) == 1 and active[0].version == 1
