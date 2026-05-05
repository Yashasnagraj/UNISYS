"""
ResoScan ML Model Training — Random Forest classifier on synthetic spectral features.

Generates synthetic training data across the healing spectrum and fracture types,
trains a RandomForestClassifier, and saves the model to disk.

Labels: Stable | Delayed Union | Non-Union | Implant Failure
Features: f_n, zeta, q_factor, tsi, spectral_bandwidth, peak_splitting_flag
"""

import os
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report


LABELS = ["Stable", "Delayed Union", "Non-Union", "Implant Failure"]
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")


def generate_synthetic_dataset(n_samples: int = 600, seed: int = 42) -> tuple:
    """Generate synthetic training data for the healing classifier.

    Creates balanced dataset across 4 healing categories with realistic
    feature distributions based on biomechanical parameters.

    Returns:
        (features_array, labels_array, feature_names)
    """
    rng = np.random.RandomState(seed)
    features = []
    labels = []

    n_per_class = n_samples // 4

    # Class 0: Stable (healed or healing well)
    for _ in range(n_per_class):
        f_n = rng.uniform(650, 850)
        zeta = rng.uniform(0.015, 0.045)
        q = 1.0 / (2.0 * zeta)
        tsi = (f_n / 850.0) * 100.0
        bw = f_n / q
        peak_split = 0
        features.append([f_n, zeta, q, tsi, bw, peak_split])
        labels.append(0)

    # Class 1: Delayed Union (slow healing, mid-range parameters)
    for _ in range(n_per_class):
        f_n = rng.uniform(400, 600)
        zeta = rng.uniform(0.05, 0.12)
        q = 1.0 / (2.0 * zeta)
        tsi = (f_n / 850.0) * 100.0
        bw = f_n / q
        peak_split = 0
        features.append([f_n, zeta, q, tsi, bw, peak_split])
        labels.append(1)

    # Class 2: Non-Union (stalled healing, poor parameters)
    for _ in range(n_per_class):
        f_n = rng.uniform(280, 420)
        zeta = rng.uniform(0.10, 0.25)
        q = 1.0 / (2.0 * zeta)
        tsi = (f_n / 850.0) * 100.0
        bw = f_n / q
        peak_split = rng.choice([0, 0, 1])  # Occasional peak splitting
        features.append([f_n, zeta, q, tsi, bw, peak_split])
        labels.append(2)

    # Class 3: Implant Failure (loose hardware, peak splitting dominant)
    for _ in range(n_per_class):
        f_n = rng.uniform(350, 700)
        zeta = rng.uniform(0.06, 0.20)
        q = 1.0 / (2.0 * zeta)
        tsi = (f_n / 850.0) * 100.0
        bw = f_n / q
        peak_split = 1  # Always has secondary peak
        features.append([f_n, zeta, q, tsi, bw, peak_split])
        labels.append(3)

    features = np.array(features)
    labels = np.array(labels)

    # Shuffle
    idx = rng.permutation(len(labels))
    features = features[idx]
    labels = labels[idx]

    feature_names = ["f_n", "zeta", "q_factor", "tsi", "spectral_bandwidth", "peak_splitting"]
    return features, labels, feature_names


def train_and_save(n_samples: int = 600):
    """Train Random Forest classifier and save to model.pkl."""
    X, y, feature_names = generate_synthetic_dataset(n_samples)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print("Classification Report:")
    print(classification_report(y_test, y_pred, target_names=LABELS))

    accuracy = clf.score(X_test, y_test)
    print(f"Accuracy: {accuracy:.3f}")

    # Save model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf, "feature_names": feature_names, "labels": LABELS}, f)

    print(f"Model saved to {MODEL_PATH}")
    return clf


if __name__ == "__main__":
    train_and_save()
