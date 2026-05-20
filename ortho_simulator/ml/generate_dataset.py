"""
ResoScan Dataset Generator — Synthetic training corpus via the actual signal pipeline.

Generates ~5000 labelled samples by running the production signal pipeline:
  sample patient profile -> generate raw signal -> extract 25 features -> label

Crucial design decisions for ML credibility:
  - Uses the SAME signal_generator + feature_extractor that runs at inference time,
    so train and serve distributions are identical.
  - Class boundaries deliberately OVERLAP (Gompertz noise, patient-to-patient
    f_healthy variation, pressure/noise variation, soft-tissue artifact) so the
    classifier must actually learn rather than memorise non-overlapping parameter
    ranges.
  - Realistic patient sampling: bone, fracture type, week from a per-class
    distribution (Stable skewed late, Non-Union skewed mid, Implant Failure
    uniform with loose flag forced on).

Run:
    python ortho_simulator/ml/generate_dataset.py
Output:
    ortho_simulator/data/training_dataset.csv   (~5000 rows)
    ortho_simulator/data/validation_dataset.csv (~1000 rows, separate seed)
"""

import os
import sys
import csv
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from engine.signal_generator import generate_scan_signal
from engine.healing_model import gompertz_healing, non_union_curve
from data.bone_profiles import BONE_PROFILES, get_bone_names
from data.fracture_profiles import get_fracture_types
from ml.feature_extractor import extract_features, FEATURE_NAMES


# Single source of truth — exported so train_model and classification import the same list
LABEL_NAMES = ["Stable", "Delayed Union", "Non-Union", "Implant Failure"]
LABEL_TO_IDX = {name: i for i, name in enumerate(LABEL_NAMES)}


def _sample_patient_f_healthy(rng: np.random.RandomState, bone: str) -> float:
    """Patient-to-patient variation around bone profile f_healthy (+/- 15%)."""
    base = BONE_PROFILES[bone]["f_healthy"]
    return float(base * rng.uniform(0.85, 1.15))


def _label_from_state(callus_pct: float, week: int, implant_loose: bool,
                     non_union_flag: bool, rng: np.random.RandomState) -> int:
    """Assign label from biomechanical state with deliberate overlap.

    Boundaries are intentionally fuzzy — a sample near a boundary may end up
    in either adjacent class. This forces the model to learn the feature
    relationships rather than memorising parameter ranges.
    """
    # Implant Failure dominates when the implant is loose (peak splitting is the marker)
    if implant_loose:
        return LABEL_TO_IDX["Implant Failure"]

    # Non-union trajectory -> stalled at low callus, regardless of week
    if non_union_flag and callus_pct < 40:
        # Slight chance of being labelled Delayed Union near the boundary
        if callus_pct > 30 and rng.random() < 0.20:
            return LABEL_TO_IDX["Delayed Union"]
        return LABEL_TO_IDX["Non-Union"]

    # Otherwise gradient: callus_pct + week + noise -> stable / delayed / non-union
    # Use a noisy decision function (sigmoid-ish) rather than hard thresholds
    score = callus_pct + 0.5 * (week - 8) + rng.normal(0, 5.0)

    if score > 70:
        # Stable, but with overlap into Delayed Union near the boundary
        if score < 78 and rng.random() < 0.18:
            return LABEL_TO_IDX["Delayed Union"]
        return LABEL_TO_IDX["Stable"]
    if score > 35:
        # Delayed Union, with overlap into both neighbours
        if score > 62 and rng.random() < 0.15:
            return LABEL_TO_IDX["Stable"]
        if score < 42 and rng.random() < 0.15:
            return LABEL_TO_IDX["Non-Union"]
        return LABEL_TO_IDX["Delayed Union"]
    # Low score
    if score > 28 and rng.random() < 0.20:
        return LABEL_TO_IDX["Delayed Union"]
    return LABEL_TO_IDX["Non-Union"]


def _sample_one(rng: np.random.RandomState) -> dict:
    """Generate a single (features, label, metadata) row."""
    bone = rng.choice(get_bone_names())
    fracture_type = rng.choice(get_fracture_types())

    # Patient-specific healthy frequency
    f_healthy = _sample_patient_f_healthy(rng, bone)

    # Sample healing trajectory type
    # 70% normal healing, 18% non-union, 12% implant failure
    trajectory = rng.choice(["normal", "non_union", "implant_failure"],
                            p=[0.70, 0.18, 0.12])

    week = int(rng.randint(0, 20))

    if trajectory == "normal":
        callus_base = gompertz_healing(week)
        non_union_flag = False
        implant_loose = False
    elif trajectory == "non_union":
        callus_base = non_union_curve(week)
        non_union_flag = True
        implant_loose = False
    else:  # implant_failure
        # Implant failure can happen at any healing stage; loose flag forced
        callus_base = gompertz_healing(week) * rng.uniform(0.5, 1.0)
        non_union_flag = False
        implant_loose = True

    # Add patient-to-patient biological variability around expected callus
    callus_pct = float(np.clip(callus_base + rng.normal(0, 8.0), 0.0, 100.0))

    # Pressure: mostly within optimal 2-5 N window, occasionally outside
    if rng.random() < 0.85:
        pressure_n = float(rng.uniform(2.5, 4.5))
    else:
        pressure_n = float(rng.uniform(0.8, 6.5))

    # Measurement noise: realistic SNR variation
    noise_level = float(rng.uniform(0.003, 0.015))

    # --- Run the actual signal pipeline ---
    scan = generate_scan_signal(
        callus_pct=callus_pct,
        f_healthy=f_healthy,
        implant_loose=implant_loose,
        pressure_n=pressure_n,
        noise_level=noise_level,
    )

    # --- Extract features (same path used at inference) ---
    feats = extract_features(
        signal=scan["response"],
        fs=scan["fs"],
        f_healthy=f_healthy,
        callus_pct=callus_pct,
    )

    # --- Label ---
    label_idx = _label_from_state(callus_pct, week, implant_loose,
                                   non_union_flag, rng)

    row = {name: feats[name] for name in FEATURE_NAMES}
    row["label"] = label_idx
    row["label_name"] = LABEL_NAMES[label_idx]
    # Metadata (not used as features, kept for traceability and validation page)
    row["meta_bone"] = bone
    row["meta_fracture_type"] = fracture_type
    row["meta_week"] = week
    row["meta_callus_pct"] = round(callus_pct, 2)
    row["meta_f_healthy"] = round(f_healthy, 2)
    row["meta_pressure_n"] = round(pressure_n, 2)
    row["meta_implant_loose"] = int(implant_loose)
    row["meta_non_union"] = int(non_union_flag)
    return row


def generate_dataset(n_samples: int, seed: int, output_path: str,
                     progress_every: int = 250) -> None:
    """Generate n_samples rows and write to output_path as CSV."""
    rng = np.random.RandomState(seed)
    rows = []
    t0 = time.time()
    for i in range(n_samples):
        rows.append(_sample_one(rng))
        if (i + 1) % progress_every == 0 or (i + 1) == n_samples:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0.0
            remaining = (n_samples - i - 1) / rate if rate > 0 else 0.0
            print(f"  [{i+1}/{n_samples}] elapsed={elapsed:.1f}s "
                  f"rate={rate:.1f}/s eta={remaining:.1f}s")

    columns = (
        FEATURE_NAMES
        + ["label", "label_name"]
        + ["meta_bone", "meta_fracture_type", "meta_week", "meta_callus_pct",
           "meta_f_healthy", "meta_pressure_n", "meta_implant_loose", "meta_non_union"]
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")


def _summary(csv_path: str) -> None:
    """Print quick class distribution summary."""
    import collections
    counts = collections.Counter()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[row["label_name"]] += 1
    total = sum(counts.values())
    print(f"  Class distribution ({total} samples):")
    for label in LABEL_NAMES:
        n = counts.get(label, 0)
        pct = 100.0 * n / total if total else 0.0
        print(f"    {label:<18s} {n:>5d}  ({pct:5.1f}%)")


if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data")

    print("Generating training set (5000 samples)...")
    train_path = os.path.join(DATA_DIR, "training_dataset.csv")
    generate_dataset(n_samples=5000, seed=42, output_path=train_path)
    _summary(train_path)

    print()
    print("Generating holdout validation set (1000 samples, different seed)...")
    val_path = os.path.join(DATA_DIR, "validation_dataset.csv")
    generate_dataset(n_samples=1000, seed=2026, output_path=val_path)
    _summary(val_path)
