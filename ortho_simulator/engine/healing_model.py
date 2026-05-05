"""
ResoScan Healing Model — 16-week Gompertz sigmoid progression.

Models fracture healing progression using a Gompertz sigmoid curve,
generating weekly TSI predictions with derived clinical parameters.
Supports both normal healing and non-union trajectories.
"""

import numpy as np


def gompertz_healing(week: float, rate: float = 0.45, inflection: float = 4.5) -> float:
    """Compute healing percentage using Gompertz sigmoid.

    S(wk) = 100 * exp(-exp(-rate * (wk - inflection)))

    Typical output:
        Wk0  →  0%
        Wk4  → 20%
        Wk8  → 55%
        Wk12 → 85%
        Wk16 → 97%
    """
    return 100.0 * np.exp(-np.exp(-rate * (week - inflection)))


def non_union_curve(week: float, plateau: float = 30.0,
                    plateau_start: float = 6.0) -> float:
    """Non-union healing trajectory — plateaus at ~30% after week 6.

    Uses a modified logistic that saturates early.
    """
    if week <= plateau_start:
        return gompertz_healing(week) * (plateau / 100.0) * 1.5
    else:
        base = gompertz_healing(plateau_start) * (plateau / 100.0) * 1.5
        # Slow drift upward (non-union still shows minimal progress)
        drift = 2.0 * np.log(1 + (week - plateau_start))
        return min(base + drift, plateau)


def generate_healing_timeline(weeks: int = 17, non_union: bool = False,
                               f_healthy: float = 850.0) -> list:
    """Generate week-by-week healing timeline data.

    For each week 0-16, computes:
        - callus_pct (healing percentage)
        - tsi (Tibial Stiffness Index)
        - f_n (resonant frequency)
        - zeta (damping ratio)
        - rust (RUST score)
        - phase (healing phase name)
        - recommendation (clinical advice)

    Returns:
        List of dicts, one per week
    """
    from engine.clinical_metrics import compute_tsi, compute_rust
    from engine.signal_generator import callus_to_frequency, callus_to_damping

    timeline = []

    for week in range(weeks):
        if non_union:
            callus_pct = non_union_curve(week)
        else:
            callus_pct = gompertz_healing(week)

        f_n = callus_to_frequency(callus_pct, f_healthy)
        zeta = callus_to_damping(callus_pct)
        tsi = compute_tsi(f_n, f_healthy)
        rust = compute_rust(tsi)
        q_factor = 1.0 / (2.0 * zeta) if zeta > 0.001 else 500.0

        # Determine phase
        if callus_pct < 15:
            phase = "Inflammatory"
        elif callus_pct < 40:
            phase = "Soft Callus"
        elif callus_pct < 70:
            phase = "Hard Callus"
        elif callus_pct < 90:
            phase = "Consolidation"
        else:
            phase = "Remodeling"

        # Recommendation
        if tsi > 80 and zeta < 0.03:
            rec = "Full weight-bearing"
        elif tsi > 60:
            rec = "Partial weight-bearing"
        elif tsi > 40:
            rec = "Touch-down weight-bearing"
        else:
            rec = "Non-weight-bearing"

        timeline.append({
            "week": week,
            "callus_pct": round(callus_pct, 1),
            "tsi": round(tsi, 1),
            "f_n": round(f_n, 1),
            "zeta": round(zeta, 4),
            "q_factor": round(q_factor, 1),
            "rust": rust,
            "phase": phase,
            "recommendation": rec,
        })

    return timeline


def get_normal_healing_band(weeks: int = 17) -> dict:
    """Compute ±1 SD band around normal healing curve.

    Returns upper and lower bounds for shading on the timeline chart.
    """
    weeks_arr = np.arange(weeks)
    center = np.array([gompertz_healing(w) for w in weeks_arr])

    # SD roughly 8-12% of max, larger in mid-healing
    sd = 8.0 + 4.0 * np.sin(np.pi * weeks_arr / 16.0)

    upper = np.clip(center + sd, 0, 100)
    lower = np.clip(center - sd, 0, 100)

    return {
        "weeks": weeks_arr.tolist(),
        "center": center.tolist(),
        "upper": upper.tolist(),
        "lower": lower.tolist(),
    }
