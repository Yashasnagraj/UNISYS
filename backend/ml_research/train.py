"""
Train the ResoScan dual-head healing-outcome predictor on the literature-grounded
synthetic cohort, and run the key ablation that proves the vibration telemetry
adds information BEYOND the validated clinical scores.

Two heads (shared early-window feature vector, t <= 6 weeks):
  * Classification head  -> outcome {normal, delayed, nonunion}   (GradientBoosting)
  * Regression head      -> weeks until safe-to-walk              (GradientBoosting)

The ablation trains the classifier on three feature sets:
  (A) clinical only        — demographics + LEG-NUI/NURD/FRACTING
  (B) vibration only       — f1 / SFI / damping + their early slopes
  (C) clinical + vibration — the full ResoScan fusion
If (C) > (A), the device measures something the clinical scores miss. That single
comparison is the project's defensible answer to "did you just re-code a formula?"

Outputs:
  * model bundle  -> ml_research/healing_predictor.pkl
  * metrics       -> ml_research/healing_metrics.json

Reproducible: fixed seeds throughout.
Run:  python -m ml_research.train
"""
from __future__ import annotations

import json
import os
import pickle

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
    precision_recall_fscore_support, r2_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from . import generate as G
from . import synth_params as P

HERE = os.path.dirname(__file__)
N_PATIENTS = 6000
SEED = 20260608


# --------------------------------------------------------------------------- #
def _cols(feature_names, subset):
    """Column indices for a feature subset."""
    return [feature_names.index(c) for c in subset]


def _ablation(X, y, feature_names):
    """5-fold CV macro-F1 for clinical-only / vibration-only / fused."""
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    out = {}
    for name, subset in [
        ("clinical_only", G.CLINICAL_FEATURES),
        ("vibration_only", G.VIBRATION_FEATURES),
        ("fused", G.ALL_FEATURES),
    ]:
        cols = _cols(feature_names, subset)
        clf = GradientBoostingClassifier(random_state=SEED)
        f1 = cross_val_score(clf, X[:, cols], y, cv=skf, scoring="f1_macro")
        acc = cross_val_score(clf, X[:, cols], y, cv=skf, scoring="accuracy")
        out[name] = {
            "n_features": len(cols),
            "f1_macro_mean": round(float(f1.mean()), 4),
            "f1_macro_std": round(float(f1.std()), 4),
            "accuracy_mean": round(float(acc.mean()), 4),
        }
    return out


def main():
    print(f"[1/5] Generating synthetic cohort (n={N_PATIENTS}) ...")
    X, y_class, y_weeks, feature_names = G.generate_cohort(N_PATIENTS, seed=SEED)
    mix = {lbl: int((y_class == i).sum()) for i, lbl in enumerate(G.OUTCOME_LABELS)}
    print(f"      outcome mix: {mix}")

    # ---- holdout split (same split for both heads) ----
    Xtr, Xte, yc_tr, yc_te, yw_tr, yw_te = train_test_split(
        X, y_class, y_weeks, test_size=0.2, random_state=SEED, stratify=y_class)

    # ---- ABLATION (the headline result) ----
    print("[2/5] Ablation: clinical-only vs vibration-only vs fused ...")
    abl = _ablation(X, y_class, feature_names)
    for k, v in abl.items():
        print(f"      {k:15s}  macro-F1={v['f1_macro_mean']:.3f}  acc={v['accuracy_mean']:.3f}")
    lift = abl["fused"]["f1_macro_mean"] - abl["clinical_only"]["f1_macro_mean"]
    print(f"      >>> vibration lift over clinical-only: +{lift:.3f} macro-F1")

    # ---- Classification head (fused, final model) ----
    print("[3/5] Training classification head (fused) ...")
    clf = GradientBoostingClassifier(random_state=SEED)
    clf.fit(Xtr, yc_tr)
    yc_pred = clf.predict(Xte)
    acc = accuracy_score(yc_te, yc_pred)
    pr, rc, f1c, sup = precision_recall_fscore_support(
        yc_te, yc_pred, labels=[0, 1, 2], zero_division=0)
    cm = confusion_matrix(yc_te, yc_pred, labels=[0, 1, 2]).tolist()
    per_class = {
        G.OUTCOME_LABELS[i]: {
            "precision": round(float(pr[i]), 4), "recall": round(float(rc[i]), 4),
            "f1": round(float(f1c[i]), 4), "support": int(sup[i]),
        } for i in range(3)
    }
    print(f"      holdout accuracy={acc:.3f}  macro-F1={f1_score(yc_te, yc_pred, average='macro'):.3f}")

    # ---- Regression head (weeks-to-walk) ----
    print("[4/5] Training regression head (weeks-to-walk) ...")
    reg = GradientBoostingRegressor(random_state=SEED)
    reg.fit(Xtr, yw_tr)
    yw_pred = reg.predict(Xte)
    mae = mean_absolute_error(yw_te, yw_pred)
    r2 = r2_score(yw_te, yw_pred)
    print(f"      weeks-to-walk MAE={mae:.2f} weeks  R^2={r2:.3f}")

    # ---- feature importances (explainability) ----
    importances = sorted(
        ({"feature": f, "importance": round(float(imp), 4)}
         for f, imp in zip(feature_names, clf.feature_importances_)),
        key=lambda d: d["importance"], reverse=True)

    # ---- persist ----
    print("[5/5] Saving model bundle + metrics ...")
    bundle = {
        "classifier": clf, "regressor": reg,
        "feature_names": feature_names, "labels": G.OUTCOME_LABELS,
        "clinical_features": G.CLINICAL_FEATURES,
        "vibration_features": G.VIBRATION_FEATURES,
        "trained_on": "literature-grounded synthetic cohort",
        "n_train": int(len(Xtr)), "seed": SEED,
    }
    with open(os.path.join(HERE, "healing_predictor.pkl"), "wb") as f:
        pickle.dump(bundle, f)

    metrics = {
        "model": "GradientBoosting dual-head (classification + regression)",
        "data": "literature-grounded synthetic (NOT real patients)",
        "n_patients": N_PATIENTS,
        "n_features": len(feature_names),
        "outcome_mix": mix,
        "ablation": abl,
        "vibration_lift_macro_f1": round(float(lift), 4),
        "classification_holdout": {
            "accuracy": round(float(acc), 4),
            "macro_f1": round(float(f1_score(yc_te, yc_pred, average="macro")), 4),
            "per_class": per_class,
            "confusion_matrix": cm,
            "labels": G.OUTCOME_LABELS,
        },
        "regression_holdout": {
            "weeks_to_walk_mae": round(float(mae), 3),
            "r2": round(float(r2), 4),
            "note": "weeks capped at 52 for non-unions",
        },
        "top_features": importances[:10],
        "honesty_note": (
            "Trained on synthetic data grounded in published parameters (see "
            "docs/TSI_PREDICTION_LITERATURE.md). Real-patient validation is pending "
            "a clinical dataset. The ablation shows the vibration telemetry adds "
            f"+{lift:.3f} macro-F1 over the validated clinical scores alone."
        ),
    }
    with open(os.path.join(HERE, "healing_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n=== SUMMARY ===")
    print(f"Fused classifier holdout accuracy : {acc*100:.1f}%")
    print(f"Vibration lift over clinical-only : +{lift:.3f} macro-F1  "
          f"({abl['clinical_only']['f1_macro_mean']:.3f} -> {abl['fused']['f1_macro_mean']:.3f})")
    print(f"Weeks-to-walk MAE                 : {mae:.2f} weeks")
    print(f"Saved: healing_predictor.pkl, healing_metrics.json")


if __name__ == "__main__":
    main()
