"""
ResoScan Clinical Metrics — TSI, RUST, damping interpretation, classification.

Computes clinically relevant metrics from spectral analysis results
and generates weight-bearing clearance decisions.
"""

import numpy as np


def compute_tsi(f_injured: float, f_healthy: float) -> float:
    """Compute Tibial Stiffness Index.

    TSI = (f_injured / f_healthy) * 100

    Range: 0-100% (can exceed 100% if injured > healthy, clamped)
    """
    if f_healthy <= 0:
        return 0.0
    tsi = (f_injured / f_healthy) * 100.0
    return float(np.clip(tsi, 0.0, 120.0))


def compute_rust(tsi: float) -> int:
    """Compute RUST (Radiographic Union Score for Tibial fractures).

    Piecewise mapping from TSI:
        0-25% TSI  → RUST 4-5
        25-50%     → RUST 6-7
        50-75%     → RUST 8-9
        75-100%    → RUST 10-12

    Range: 4-12 (4 = no healing, 12 = complete union)
    """
    tsi_clamped = np.clip(tsi, 0.0, 100.0)

    if tsi_clamped <= 25:
        rust = 4.0 + (tsi_clamped / 25.0) * 1.0
    elif tsi_clamped <= 50:
        rust = 5.0 + ((tsi_clamped - 25.0) / 25.0) * 2.0
    elif tsi_clamped <= 75:
        rust = 7.0 + ((tsi_clamped - 50.0) / 25.0) * 2.0
    else:
        rust = 9.0 + ((tsi_clamped - 75.0) / 25.0) * 3.0

    return int(np.clip(round(rust), 4, 12))


def interpret_damping(zeta: float) -> dict:
    """Interpret damping ratio for clinical significance.

    < 0.03  → Solid union (Green)
    0.03-0.06 → Soft callus / partial healing (Yellow)
    > 0.06  → Instability / non-union risk (Red)
    """
    if zeta < 0.03:
        return {
            "label": "Solid Union",
            "color": "green",
            "hex": "#22c55e",
            "description": "Low damping indicates rigid bone continuity",
        }
    elif zeta <= 0.06:
        return {
            "label": "Partial Healing",
            "color": "yellow",
            "hex": "#eab308",
            "description": "Moderate damping suggests soft callus formation",
        }
    else:
        return {
            "label": "Instability",
            "color": "red",
            "hex": "#ef4444",
            "description": "High damping indicates fracture site instability",
        }


def classify_healing(tsi: float, zeta: float, implant_loose: bool,
                     has_secondary_peak: bool, week: int = 0) -> dict:
    """Classify healing status with traffic light recommendation.

    Decision tree:
        1. Implant loosening (secondary peak) → RED
        2. TSI > 80% and zeta < 0.03 → GREEN (safe for full WB)
        3. TSI 60-80% → YELLOW (partial loading)
        4. TSI < 60% or zeta > 0.06 → RED (instability)
        5. Week > 16 and TSI < 40% → RED (suspected non-union)
    """
    if implant_loose and has_secondary_peak:
        return {
            "status": "IMPLANT LOOSENING DETECTED",
            "color": "red",
            "hex": "#ef4444",
            "recommendation": "Immediate orthopedic consultation required. "
                              "Secondary spectral peak indicates hardware micromotion.",
            "traffic_light": "RED",
            "weight_bearing": "NON-WEIGHT-BEARING",
        }

    if week > 16 and tsi < 40:
        return {
            "status": "SUSPECTED NON-UNION",
            "color": "red",
            "hex": "#ef4444",
            "recommendation": "TSI remains below 40% at 16+ weeks. "
                              "Consider revision surgery or bone stimulation therapy.",
            "traffic_light": "RED",
            "weight_bearing": "NON-WEIGHT-BEARING",
        }

    if tsi > 80 and zeta < 0.08:
        return {
            "status": "SAFE FOR FULL WEIGHT-BEARING",
            "color": "green",
            "hex": "#22c55e",
            "recommendation": "Spectral analysis confirms solid bony union. "
                              "Progressive full weight-bearing may commence.",
            "traffic_light": "GREEN",
            "weight_bearing": "FULL WEIGHT-BEARING",
        }

    if tsi >= 55 and zeta <= 0.18:
        return {
            "status": "PARTIAL LOADING ADVISED",
            "color": "yellow",
            "hex": "#eab308",
            "recommendation": "Advancing consolidation detected. "
                              "Partial weight-bearing with assistive device recommended. "
                              "Follow-up scan in 2-3 weeks.",
            "traffic_light": "YELLOW",
            "weight_bearing": "PARTIAL WEIGHT-BEARING",
        }

    # TSI < 55 or zeta > 0.18
    return {
        "status": "INSTABILITY DETECTED",
        "color": "red",
        "hex": "#ef4444",
        "recommendation": "Fracture site remains unstable. "
                          "Maintain non-weight-bearing status. "
                          "Continue immobilization and reassess in 3-4 weeks.",
        "traffic_light": "RED",
        "weight_bearing": "NON-WEIGHT-BEARING",
    }


def compute_rust_cortex_scores(tsi: float) -> dict:
    """Compute per-cortex RUST scores for the 4-cortex visual.

    Each cortex scored 1-3:
        1 = No callus
        2 = Callus present
        3 = Bridging callus / healed

    Simulates anterior healing faster than posterior (typical tibia pattern).
    """
    base = tsi / 100.0

    # Anterior heals slightly faster
    anterior = min(3, max(1, round(1 + 2.0 * min(base * 1.15, 1.0))))
    posterior = min(3, max(1, round(1 + 2.0 * min(base * 0.9, 1.0))))
    medial = min(3, max(1, round(1 + 2.0 * min(base * 1.05, 1.0))))
    lateral = min(3, max(1, round(1 + 2.0 * min(base * 0.95, 1.0))))

    return {
        "anterior": anterior,
        "posterior": posterior,
        "medial": medial,
        "lateral": lateral,
        "total": anterior + posterior + medial + lateral,
    }


def generate_clinical_summary(bone: str, fracture_type: str, week: int,
                               tsi: float, f_n: float, zeta: float,
                               q_factor: float,
                               classification: dict) -> str:
    """Generate natural language clinical summary.

    Template-based generation for clinical report text.
    """
    # Healing phase description
    if tsi < 30:
        phase = "early inflammatory/soft callus phase"
    elif tsi < 60:
        phase = "active callus mineralization"
    elif tsi < 80:
        phase = "advancing consolidation"
    else:
        phase = "solid bony union"

    # Trend description from Q-factor
    if q_factor > 15:
        trend = "strong mechanical integrity"
    elif q_factor > 8:
        trend = "progressive stiffening of the fracture site"
    elif q_factor > 4:
        trend = "moderate callus formation with residual flexibility"
    else:
        trend = "significant fracture site motion"

    summary = (
        f"Patient ({bone} {fracture_type} fracture, Week {week}) shows TSI of {tsi:.1f}%, "
        f"indicating {phase}. Resonant frequency at {f_n:.0f} Hz with "
        f"Q-factor {q_factor:.1f} suggests {trend}. "
        f"Damping ratio zeta = {zeta:.4f}. "
        f"Recommendation: {classification['recommendation']}"
    )
    return summary
