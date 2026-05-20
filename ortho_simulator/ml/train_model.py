"""
ResoScan Model Training — Stratified 5-fold CV + holdout, multi-model selection.

Trains RandomForest and GradientBoosting on the synthetic training corpus
produced by generate_dataset.py, then selects the best model via cross-validated
F1-macro, evaluates on a held-out 20% split and a separate validation_dataset.csv.

Artifacts written to ortho_simulator/ml/artifacts/:
    model.pkl                 -- best model bundle (model + feature_names + labels)
    metrics.json              -- CV/holdout/validation metrics in machine-readable form
    confusion_matrix.png      -- static PNG (generated offline, committed)
    roc_curves.png            -- static PNG
    feature_importance.png    -- static PNG
    learning_curve.png        -- static PNG

PNGs are generated here and committed to the repo (guardrail: Streamlit Cloud
may lack kaleido/headless deps; never call fig.write_image() at app runtime).

Run:
    python ortho_simulator/ml/train_model.py
"""

import os
import sys
import json
import pickle
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import (
    StratifiedKFold, cross_val_score, train_test_split, learning_curve,
)
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_curve, auc,
    precision_recall_fscore_support, accuracy_score,
)
from sklearn.preprocessing import label_binarize

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ml.feature_extractor import FEATURE_NAMES
from ml.generate_dataset import LABEL_NAMES


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
ARTIFACTS_DIR = os.path.join(HERE, "artifacts")
MODEL_PATH = os.path.join(HERE, "model.pkl")

TRAIN_CSV = os.path.join(DATA_DIR, "training_dataset.csv")
VAL_CSV = os.path.join(DATA_DIR, "validation_dataset.csv")

N_FOLDS = 5
RANDOM_STATE = 42


def _load_xy(csv_path: str):
    df = pd.read_csv(csv_path)
    X = df[FEATURE_NAMES].values
    y = df["label"].values
    return X, y, df


def _candidate_models():
    """Light hyperparameter grid for two ensemble families."""
    return [
        ("RandomForest_d10", RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_leaf=3,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1)),
        ("RandomForest_d14", RandomForestClassifier(
            n_estimators=200, max_depth=14, min_samples_leaf=2,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1)),
        ("GradientBoosting", GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.08,
            random_state=RANDOM_STATE)),
    ]


def _cv_score(model, X, y):
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True,
                          random_state=RANDOM_STATE)
    f1_scores = cross_val_score(model, X, y, cv=skf, scoring="f1_macro", n_jobs=-1)
    acc_scores = cross_val_score(model, X, y, cv=skf, scoring="accuracy", n_jobs=-1)
    return f1_scores, acc_scores


def _save_confusion_matrix_png(cm, labels, path):
    fig = go.Figure(data=go.Heatmap(
        z=cm,
        x=labels, y=labels,
        text=cm, texttemplate="%{text}",
        colorscale="Blues",
        colorbar=dict(title="Count"),
    ))
    fig.update_layout(
        title="Confusion Matrix (Holdout Set)",
        xaxis_title="Predicted",
        yaxis_title="Actual",
        width=600, height=550,
        yaxis_autorange="reversed",
    )
    fig.write_image(path, scale=2)


def _save_roc_png(y_test, y_proba, labels, path):
    y_bin = label_binarize(y_test, classes=list(range(len(labels))))
    fig = go.Figure()
    for i, label in enumerate(labels):
        if y_bin.shape[1] == 1:
            # binary case
            fpr, tpr, _ = roc_curve(y_bin, y_proba[:, i])
        else:
            fpr, tpr, _ = roc_curve(y_bin[:, i], y_proba[:, i])
        a = auc(fpr, tpr)
        fig.add_trace(go.Scatter(x=fpr, y=tpr, name=f"{label} (AUC={a:.3f})",
                                  mode="lines"))
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], name="chance",
                              mode="lines",
                              line=dict(dash="dash", color="gray")))
    fig.update_layout(
        title="ROC Curves (One-vs-Rest)",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        width=650, height=550,
    )
    fig.write_image(path, scale=2)


def _save_feature_importance_png(model, feature_names, path):
    if not hasattr(model, "feature_importances_"):
        return
    importances = model.feature_importances_
    order = np.argsort(importances)[::-1]
    names = [feature_names[i] for i in order]
    vals = [importances[i] for i in order]
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h",
        marker=dict(color="#1f77b4"),
    ))
    fig.update_layout(
        title="Feature Importance",
        xaxis_title="Mean Decrease in Impurity",
        yaxis_title="",
        width=700, height=700,
        yaxis_autorange="reversed",
        margin=dict(l=180),
    )
    fig.write_image(path, scale=2)


def _save_learning_curve_png(model, X, y, path):
    train_sizes, train_scores, test_scores = learning_curve(
        model, X, y, cv=3, scoring="f1_macro",
        train_sizes=np.linspace(0.1, 1.0, 6), n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    train_mean = train_scores.mean(axis=1)
    train_std = train_scores.std(axis=1)
    test_mean = test_scores.mean(axis=1)
    test_std = test_scores.std(axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=train_sizes, y=train_mean, name="Training F1",
                              mode="lines+markers",
                              error_y=dict(type="data", array=train_std)))
    fig.add_trace(go.Scatter(x=train_sizes, y=test_mean, name="CV F1",
                              mode="lines+markers",
                              error_y=dict(type="data", array=test_std)))
    fig.update_layout(
        title="Learning Curve",
        xaxis_title="Training samples",
        yaxis_title="F1 (macro)",
        width=650, height=450,
    )
    fig.write_image(path, scale=2)


def main():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    if not os.path.exists(TRAIN_CSV):
        print(f"ERROR: training data not found at {TRAIN_CSV}")
        print("Run: python ortho_simulator/ml/generate_dataset.py")
        sys.exit(1)

    print(f"Loading training set from {TRAIN_CSV}")
    X, y, _df = _load_xy(TRAIN_CSV)
    print(f"  {X.shape[0]} samples, {X.shape[1]} features")

    # --- Stratified train/holdout split ---
    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )

    # --- 5-fold CV across candidate models ---
    print(f"\nRunning {N_FOLDS}-fold stratified CV on candidate models...")
    cv_results = {}
    best_name = None
    best_f1 = -1.0
    best_estimator = None

    for name, model in _candidate_models():
        f1, acc = _cv_score(model, X_train, y_train)
        cv_results[name] = {
            "f1_macro_mean": float(f1.mean()),
            "f1_macro_std": float(f1.std()),
            "f1_macro_folds": [float(v) for v in f1],
            "accuracy_mean": float(acc.mean()),
            "accuracy_std": float(acc.std()),
        }
        print(f"  {name:<22s} F1={f1.mean():.4f} +/- {f1.std():.4f}  "
              f"acc={acc.mean():.4f} +/- {acc.std():.4f}")
        if f1.mean() > best_f1:
            best_f1 = f1.mean()
            best_name = name
            best_estimator = model

    print(f"\nBest model by CV F1-macro: {best_name} ({best_f1:.4f})")

    # --- Fit best on full training set ---
    print("Fitting best model on full training set...")
    best_estimator.fit(X_train, y_train)

    # --- Holdout evaluation ---
    print("\nHoldout evaluation...")
    y_pred = best_estimator.predict(X_holdout)
    y_proba = best_estimator.predict_proba(X_holdout)

    holdout_acc = float(accuracy_score(y_holdout, y_pred))
    precision, recall, f1_per, support = precision_recall_fscore_support(
        y_holdout, y_pred, labels=list(range(len(LABEL_NAMES))), zero_division=0,
    )
    cm = confusion_matrix(y_holdout, y_pred,
                          labels=list(range(len(LABEL_NAMES))))

    print(classification_report(y_holdout, y_pred,
                                target_names=LABEL_NAMES, zero_division=0))
    print(f"Holdout accuracy: {holdout_acc:.4f}")

    # --- External validation set (separate seed) ---
    val_metrics = None
    if os.path.exists(VAL_CSV):
        print(f"\nExternal validation on {VAL_CSV}...")
        X_val, y_val, _ = _load_xy(VAL_CSV)
        y_val_pred = best_estimator.predict(X_val)
        val_acc = float(accuracy_score(y_val, y_val_pred))
        val_prec, val_rec, val_f1, _ = precision_recall_fscore_support(
            y_val, y_val_pred, labels=list(range(len(LABEL_NAMES))),
            zero_division=0,
        )
        val_metrics = {
            "accuracy": val_acc,
            "per_class": {
                LABEL_NAMES[i]: {
                    "precision": float(val_prec[i]),
                    "recall": float(val_rec[i]),
                    "f1": float(val_f1[i]),
                } for i in range(len(LABEL_NAMES))
            },
        }
        print(f"  validation accuracy: {val_acc:.4f}")

    # --- Save PNG artifacts (offline, committed to repo) ---
    print("\nGenerating static PNG artifacts...")
    try:
        _save_confusion_matrix_png(
            cm, LABEL_NAMES,
            os.path.join(ARTIFACTS_DIR, "confusion_matrix.png"))
        _save_roc_png(
            y_holdout, y_proba, LABEL_NAMES,
            os.path.join(ARTIFACTS_DIR, "roc_curves.png"))
        _save_feature_importance_png(
            best_estimator, FEATURE_NAMES,
            os.path.join(ARTIFACTS_DIR, "feature_importance.png"))
        _save_learning_curve_png(
            best_estimator, X_train, y_train,
            os.path.join(ARTIFACTS_DIR, "learning_curve.png"))
        print("  PNGs saved to", ARTIFACTS_DIR)
    except Exception as e:
        print(f"  WARNING: PNG export failed ({e}). Validation page will fall "
              "back to in-app Plotly rendering.")

    # --- Save model bundle ---
    bundle = {
        "model": best_estimator,
        "model_name": best_name,
        "feature_names": FEATURE_NAMES,
        "labels": LABEL_NAMES,
        "trained_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)
    print(f"\nSaved model to {MODEL_PATH}")

    # --- Save metrics.json ---
    metrics = {
        "model_name": best_name,
        "trained_at": bundle["trained_at"],
        "n_train_samples": int(X_train.shape[0]),
        "n_holdout_samples": int(X_holdout.shape[0]),
        "n_features": int(X_train.shape[1]),
        "feature_names": FEATURE_NAMES,
        "labels": LABEL_NAMES,
        "cv_results": cv_results,
        "cv_best": {
            "model": best_name,
            "f1_macro_mean": float(best_f1),
            "f1_macro_std": float(cv_results[best_name]["f1_macro_std"]),
            "accuracy_mean": float(cv_results[best_name]["accuracy_mean"]),
            "accuracy_std": float(cv_results[best_name]["accuracy_std"]),
        },
        "holdout": {
            "accuracy": holdout_acc,
            "per_class": {
                LABEL_NAMES[i]: {
                    "precision": float(precision[i]),
                    "recall": float(recall[i]),
                    "f1": float(f1_per[i]),
                    "support": int(support[i]),
                } for i in range(len(LABEL_NAMES))
            },
            "confusion_matrix": cm.tolist(),
        },
        "external_validation": val_metrics,
    }
    with open(os.path.join(ARTIFACTS_DIR, "metrics.json"), "w",
              encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics to {os.path.join(ARTIFACTS_DIR, 'metrics.json')}")


if __name__ == "__main__":
    main()
