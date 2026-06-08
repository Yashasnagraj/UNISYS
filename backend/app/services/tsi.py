"""
Canonical Tibial Stiffness Index — the literature-correct SQUARED form.

    TSI = (f_fracture / f_healthy)^2 * 100

Precedent: Tower, Beals & Duwelius (1993) J Orthop Trauma 7(6):552 (n=74,
p=0.0001) coined "Tibial Stiffness Index"; Mattei et al. (2021) Int Biomechanics
8(1) use the identical "Squared Frequency Index". Physically, f^2 is proportional
to stiffness k for a damped oscillator (Pelker & Saha 1983). Matches the firmware
(stiffness.c) and the hardware interface spec.

Because squaring is non-linear, clinical thresholds are re-derived from the
legacy linear scale so decisions stay invariant:  T_sq = (T_lin/100)^2 * 100.
"""
from __future__ import annotations


def compute_tsi_squared(f_fracture: float, f_healthy: float) -> float:
    if f_healthy <= 0:
        return 0.0
    val = (float(f_fracture) / float(f_healthy)) ** 2 * 100.0
    return float(max(0.0, min(120.0, val)))


def compute_tsi_linear(f_fracture: float, f_healthy: float) -> float:
    """Legacy linear ratio, kept so the UI can show both numbers."""
    if f_healthy <= 0:
        return 0.0
    val = (float(f_fracture) / float(f_healthy)) * 100.0
    return float(max(0.0, min(120.0, val)))


def _sq(t_lin: float) -> float:
    return (t_lin / 100.0) ** 2 * 100.0


# Thresholds on the SQUARED scale (linear 80 -> 64, linear 55 -> ~30).
TSI_FULL_WB = _sq(80.0)      # ~64.0  -> full weight-bearing
TSI_PARTIAL_WB = _sq(55.0)   # ~30.25 -> partial weight-bearing
TSI_NONUNION = _sq(40.0)     # ~16.0  -> non-union concern


def classify_traffic_light(tsi_sq: float, zeta: float | None = None,
                           week: float = 0.0, has_secondary: bool = False) -> dict:
    """Traffic-light decision on the squared-TSI scale (decision-invariant vs
    the engine's linear thresholds)."""
    if has_secondary:
        return {"traffic_light": "red", "recommendation": "Loose hardware suspected — surgical review",
                "weight_bearing": "none"}
    if week > 16 and tsi_sq < TSI_NONUNION:
        return {"traffic_light": "red", "recommendation": "Suspected non-union — consider surgery",
                "weight_bearing": "none"}
    if tsi_sq >= TSI_FULL_WB and (zeta is None or zeta < 0.08):
        return {"traffic_light": "green", "recommendation": "Safe for full weight-bearing",
                "weight_bearing": "full"}
    if tsi_sq >= TSI_PARTIAL_WB and (zeta is None or zeta <= 0.18):
        return {"traffic_light": "amber", "recommendation": "Partial weight-bearing — follow up in 2-3 weeks",
                "weight_bearing": "partial"}
    return {"traffic_light": "red", "recommendation": "Maintain non-weight-bearing — reassess in 3-4 weeks",
            "weight_bearing": "none"}
