"""
ResoScan Personalised Healing Prediction.

Given a patient's history of (weeks-since-fracture, TSI) measurements, fit a
Gompertz healing curve to *their* trajectory, then extrapolate to the
clinical weight-bearing threshold (TSI = 80%) and report the estimated
number of days remaining.

Gompertz model (matches engine.healing_model):
    TSI(t) = 100 * exp(-exp(-k * (t - t0)))

Two free parameters per patient:
    k   -- growth rate (1/week). Healthy young adults: ~0.45. Smokers,
           elderly, diabetics heal slower: k -> 0.30-0.40.
    t0  -- inflection time (weeks). Typically 4-5 weeks; later for
           complex fractures.

Demographic adjustment of priors (Hak 2014, Adams 2018, Marquez-Lara 2016):
    smoker:    k_prior *= 0.65   (~35% slower union)
    diabetic:  k_prior *= 0.75
    age >= 65: k_prior *= 0.80

The prior shifts the initial guess for curve_fit; the actual k for the
patient is whatever best fits their measured trajectory.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit


# Population-average priors (matches engine.healing_model.gompertz_healing)
PRIOR_K = 0.45
PRIOR_T0 = 4.5

# Clinical weight-bearing threshold
TSI_TARGET_PCT = 80.0


@dataclass
class PatientPrediction:
    """Result of fitting a patient's healing trajectory."""
    fitted_k: float                 # personal Gompertz rate
    fitted_t0: float                # personal inflection week
    weeks_to_target: Optional[float]  # weeks from fracture to TSI 80%
    weeks_remaining: Optional[float]  # from latest scan
    days_remaining: Optional[int]
    target_date: Optional[date]
    current_tsi_pct: float          # most recent scan TSI
    current_week: float             # weeks since fracture at latest scan
    pace_vs_population: str         # "ahead" | "on pace" | "behind"
    pace_delta_days: int            # +ve means slower than population
    confidence: str                 # "low" | "moderate" | "high"


def _gompertz(t: np.ndarray, k: float, t0: float) -> np.ndarray:
    return 100.0 * np.exp(-np.exp(-k * (t - t0)))


def _gompertz_inverse(target_tsi: float, k: float, t0: float) -> Optional[float]:
    """Solve for the week at which TSI(t) = target_tsi.

    Returns None if target is unreachable for this Gompertz (k <= 0).
    """
    if k <= 0 or target_tsi <= 0 or target_tsi >= 100:
        return None
    # target = 100 * exp(-exp(-k*(t - t0)))
    # exp(-k*(t - t0)) = -ln(target/100)
    inner = -np.log(target_tsi / 100.0)
    if inner <= 0:
        return None
    # -k*(t - t0) = ln(inner)
    return float(t0 - np.log(inner) / k)


def demographic_k_prior(
    smoker: bool = False,
    diabetic: bool = False,
    age: int = 35,
) -> float:
    """Adjust the rate prior based on demographics. Used to seed curve_fit
    and to gauge whether the patient is healing fast or slow vs *their own*
    expected curve, not just the population average."""
    k = PRIOR_K
    if smoker:
        k *= 0.65
    if diabetic:
        k *= 0.75
    if age >= 65:
        k *= 0.80
    elif age >= 50:
        k *= 0.92
    return k


def predict(
    scan_weeks: list[float],
    scan_tsi: list[float],
    fracture_date: date,
    today: date,
    smoker: bool = False,
    diabetic: bool = False,
    age: int = 35,
) -> PatientPrediction:
    """Fit a personalised Gompertz curve and predict days to weight-bearing.

    Args:
        scan_weeks:    weeks since fracture for each past scan (float)
        scan_tsi:      TSI value at each past scan (percent, 0-100)
        fracture_date: when the fracture happened
        today:         current date (for date-of-clearance projection)
        smoker, diabetic, age: demographics (seed the prior, NOT a hard rule)
    """
    if len(scan_weeks) != len(scan_tsi) or len(scan_weeks) == 0:
        raise ValueError("scan_weeks and scan_tsi must be non-empty and equal length")

    weeks = np.asarray(scan_weeks, dtype=float)
    tsi = np.asarray(scan_tsi, dtype=float)

    k_prior = demographic_k_prior(smoker, diabetic, age)

    # Fit personalised Gompertz. Bounds prevent pathological negative k or
    # absurdly delayed inflection.
    try:
        if len(weeks) >= 3:
            popt, _ = curve_fit(
                _gompertz, weeks, tsi,
                p0=[k_prior, PRIOR_T0],
                bounds=([0.05, 0.0], [2.0, 30.0]),
                maxfev=2000,
            )
            k_fit, t0_fit = float(popt[0]), float(popt[1])
            confidence = "high" if len(weeks) >= 4 else "moderate"
        elif len(weeks) == 2:
            # Two-point fit: estimate k from slope, infer t0
            popt, _ = curve_fit(
                _gompertz, weeks, tsi,
                p0=[k_prior, PRIOR_T0],
                bounds=([0.05, 0.0], [2.0, 30.0]),
                maxfev=2000,
            )
            k_fit, t0_fit = float(popt[0]), float(popt[1])
            confidence = "moderate"
        else:
            # Single scan: use demographic prior, anchor t0 so the curve passes
            # through the single observed point.
            k_fit = k_prior
            tsi_val = max(min(tsi[0], 99.9), 0.1)
            inner = -np.log(tsi_val / 100.0)
            if inner > 0:
                t0_fit = float(weeks[0] + np.log(inner) / k_fit)
            else:
                t0_fit = PRIOR_T0
            confidence = "low"
    except Exception:
        k_fit, t0_fit = k_prior, PRIOR_T0
        confidence = "low"

    # Where does the personal curve hit TSI=80?
    weeks_to_target = _gompertz_inverse(TSI_TARGET_PCT, k_fit, t0_fit)

    current_week = float(weeks[-1])
    current_tsi = float(tsi[-1])

    # Override: if the most recent MEASURED TSI is already at/above target,
    # patient is cleared regardless of where the fitted curve crosses.
    if current_tsi >= TSI_TARGET_PCT:
        weeks_remaining = 0.0
        days_remaining = 0
        target_date = today
    elif weeks_to_target is not None and weeks_to_target > current_week:
        weeks_remaining = weeks_to_target - current_week
        days_remaining = int(round(weeks_remaining * 7.0))
        # Sanity: if extrapolation says >26 weeks (~6 months), treat as
        # non-union risk rather than reporting an implausibly distant date.
        if weeks_remaining > 26.0:
            weeks_remaining = None
            days_remaining = None
            target_date = None
        else:
            target_date = today + timedelta(days=days_remaining)
    elif weeks_to_target is not None and weeks_to_target <= current_week:
        # Fitted curve already crossed but measured value didn't yet — trust
        # the measurement, recommend continued monitoring rather than instant
        # clearance.
        weeks_remaining = 0.5  # ~3.5 days
        days_remaining = 4
        target_date = today + timedelta(days=days_remaining)
    else:
        weeks_remaining = None
        days_remaining = None
        target_date = None

    # Pace vs the population-average curve (PRIOR_K, PRIOR_T0)
    pop_target_week = _gompertz_inverse(TSI_TARGET_PCT, PRIOR_K, PRIOR_T0)
    if weeks_to_target is not None and pop_target_week is not None:
        delta_weeks = weeks_to_target - pop_target_week
        pace_delta_days = int(round(delta_weeks * 7.0))
        if delta_weeks < -0.5:
            pace = "ahead"
        elif delta_weeks > 0.5:
            pace = "behind"
        else:
            pace = "on pace"
    else:
        pace = "on pace"
        pace_delta_days = 0

    return PatientPrediction(
        fitted_k=k_fit,
        fitted_t0=t0_fit,
        weeks_to_target=weeks_to_target,
        weeks_remaining=weeks_remaining,
        days_remaining=days_remaining,
        target_date=target_date,
        current_tsi_pct=current_tsi,
        current_week=current_week,
        pace_vs_population=pace,
        pace_delta_days=pace_delta_days,
        confidence=confidence,
    )


def fitted_curve_points(
    pred: PatientPrediction,
    max_week: float = 20.0,
    n: int = 100,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate (week, TSI) points along the fitted personal curve for plotting."""
    weeks = np.linspace(0.0, max_week, n)
    tsi = _gompertz(weeks, pred.fitted_k, pred.fitted_t0)
    return weeks, tsi


def population_curve_points(
    max_week: float = 20.0, n: int = 100,
) -> tuple[np.ndarray, np.ndarray]:
    weeks = np.linspace(0.0, max_week, n)
    tsi = _gompertz(weeks, PRIOR_K, PRIOR_T0)
    return weeks, tsi
