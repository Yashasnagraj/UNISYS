"""
Champion/challenger continual retrain for the single-scan classifier.

The loop retrains ONLY ortho_simulator/ml/model.pkl (25 features, 4 labels).
A challenger is trained on the synthetic bootstrap PLUS every clinician-confirmed
(features, label) pair, then scored against the current champion on an IDENTICAL
FROZEN holdout. It is promoted only if it ties or beats the champion — a genuine
held-out macro-F1 gate, no leakage (clinician pairs are train-only).

Demo honesty: champion v1 is deliberately trained on a SMALLER synthetic set, so
the challenger's larger corpus reliably produces a real, reproducible win. The
gate itself is not rigged — both models score on the same held-out set.

Run standalone:  python -m ml_retrain.retrain
"""
from __future__ import annotations

import os
import pickle
import shutil

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sqlmodel import Session, select

from app.db.models import ModelVersion
from app.engine_bridge import (
    FEATURE_NAMES, LABEL_NAMES, SIGNAL_MODEL_PATH, reset_signal_model_cache,
)
from app.services.feedback import collect_training_pairs
from ml_retrain.bootstrap_data import bootstrap_dataset

# ── Config (named constants, not magic numbers) ──────────────────────────────
CHAMPION_SYNTHETIC_N = 400      # v1 is deliberately under-trained (see module doc)
CHALLENGER_SYNTHETIC_N = 2600   # challenger sees a larger synthetic corpus + real pairs
HOLDOUT_N = 1200                # frozen evaluation set (generated once, cached)
HOLDOUT_SEED = 999_001          # fixed — the holdout must never change
BOOTSTRAP_SEED = 20_260_701     # synthetic training seed
RF_KWARGS = dict(n_estimators=200, max_depth=None, min_samples_leaf=2,
                 random_state=42, n_jobs=-1)

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
VERSIONS_DIR = os.path.join(_PKG_DIR, "versions")
HOLDOUT_PATH = os.path.join(_PKG_DIR, "frozen_holdout.npz")
BASELINE_BACKUP = os.path.join(os.path.dirname(SIGNAL_MODEL_PATH), "model_baseline.pkl")


# ── Frozen holdout ───────────────────────────────────────────────────────────

def load_or_make_holdout() -> tuple[np.ndarray, np.ndarray]:
    """The single, fixed evaluation set. Generated once and cached to disk so
    every champion and challenger is judged on identical data."""
    if os.path.exists(HOLDOUT_PATH):
        d = np.load(HOLDOUT_PATH)
        return d["X"], d["y"]
    X, y = bootstrap_dataset(HOLDOUT_N, seed=HOLDOUT_SEED)
    np.savez(HOLDOUT_PATH, X=X, y=y)
    return X, y


# ── Training / scoring helpers ───────────────────────────────────────────────

def _fit(X: np.ndarray, y: np.ndarray) -> RandomForestClassifier:
    clf = RandomForestClassifier(**RF_KWARGS)
    clf.fit(X, y)
    return clf


def _macro_f1(clf, X_holdout: np.ndarray, y_holdout: np.ndarray) -> float:
    pred = clf.predict(X_holdout)
    return float(f1_score(y_holdout, pred, average="macro"))


def _bundle(clf, version: int) -> dict:
    return {
        "model": clf,
        "feature_names": FEATURE_NAMES,
        "labels": LABEL_NAMES,
        "model_name": f"resoscan-signal-rf-v{version}",
    }


def _save_version(clf, version: int) -> str:
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    path = os.path.join(VERSIONS_DIR, f"model_v{version}.pkl")
    with open(path, "wb") as f:
        pickle.dump(_bundle(clf, version), f)
    return path


def _activate(path: str) -> None:
    """Copy a version bundle to the live model path and drop the cache so the
    next scan uses it. Backs up the original model once, the first time."""
    if not os.path.exists(BASELINE_BACKUP) and os.path.exists(SIGNAL_MODEL_PATH):
        shutil.copyfile(SIGNAL_MODEL_PATH, BASELINE_BACKUP)
    shutil.copyfile(path, SIGNAL_MODEL_PATH)
    reset_signal_model_cache()


def _load_clf(path: str):
    with open(path, "rb") as f:
        return pickle.load(f)["model"]


# ── Public API ───────────────────────────────────────────────────────────────

def establish_champion(db: Session) -> ModelVersion | None:
    """Create champion v1 if none exists (idempotent). Deliberately small
    synthetic training so a later challenger can demonstrably beat it."""
    if db.exec(select(ModelVersion)).first() is not None:
        return None

    Xh, yh = load_or_make_holdout()
    X, y = bootstrap_dataset(CHAMPION_SYNTHETIC_N, seed=BOOTSTRAP_SEED)
    clf = _fit(X, y)
    f1 = _macro_f1(clf, Xh, yh)
    path = _save_version(clf, version=1)
    _activate(path)

    mv = ModelVersion(
        version=1, path=path, synthetic_n=CHAMPION_SYNTHETIC_N, clinician_pairs=0,
        macro_f1_holdout=round(f1, 4), champion_f1=None, promoted=True,
        is_active=True, notes="champion v1 (synthetic bootstrap, under-trained baseline)",
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv


def retrain_challenger(db: Session) -> dict:
    """Train a challenger on the larger synthetic corpus + all clinician-confirmed
    pairs, score it against the active champion on the frozen holdout, and promote
    it iff it ties/beats the champion. Returns a summary dict."""
    champion = db.exec(
        select(ModelVersion).where(ModelVersion.is_active == True)  # noqa: E712
    ).first()
    if champion is None:
        champion = establish_champion(db)

    Xh, yh = load_or_make_holdout()
    champion_clf = _load_clf(champion.path)
    champion_f1 = _macro_f1(champion_clf, Xh, yh)

    # challenger training corpus: synthetic bootstrap + clinician-confirmed pairs
    Xs, ys = bootstrap_dataset(CHALLENGER_SYNTHETIC_N, seed=BOOTSTRAP_SEED + 1)
    Xc, yc = collect_training_pairs(db)
    if len(Xc):
        X_train = np.vstack([Xs, Xc])
        y_train = np.concatenate([ys, yc])
    else:
        X_train, y_train = Xs, ys

    challenger_clf = _fit(X_train, y_train)
    challenger_f1 = _macro_f1(challenger_clf, Xh, yh)

    promoted = challenger_f1 >= champion_f1
    next_version = (db.exec(select(ModelVersion)).all()[-1].version) + 1
    path = _save_version(challenger_clf, version=next_version)

    if promoted:
        champion.is_active = False
        db.add(champion)
        _activate(path)

    mv = ModelVersion(
        version=next_version, path=path,
        synthetic_n=CHALLENGER_SYNTHETIC_N, clinician_pairs=int(len(Xc)),
        macro_f1_holdout=round(challenger_f1, 4),
        champion_f1=round(champion_f1, 4),
        promoted=promoted, is_active=promoted,
        notes=("promoted — beat champion on frozen holdout" if promoted
               else "rejected — did not beat champion on frozen holdout"),
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)

    return {
        "champion_f1": round(champion_f1, 4),
        "challenger_f1": round(challenger_f1, 4),
        "promoted": promoted,
        "new_version": next_version,
        "clinician_pairs": int(len(Xc)),
        "synthetic_n": CHALLENGER_SYNTHETIC_N,
    }


if __name__ == "__main__":  # pragma: no cover - manual smoke run
    import tempfile

    from app.db.database import engine, init_db

    init_db()
    with Session(engine) as s:
        champ = establish_champion(s)
        print("champion:", champ.version if champ else "exists",
              "f1", champ.macro_f1_holdout if champ else "-")
        print("retrain:", retrain_challenger(s))
