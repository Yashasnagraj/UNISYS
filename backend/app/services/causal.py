"""
ResoScan causal explanation layer.

A hand-coded clinical DAG of the established drivers of bone-healing rate. It is
NOT a fitted model — the edges encode direction and relative strength from the
orthopaedic literature, so a verdict can be explained in causal terms ("flagged
Delayed because smoker + week 12 + low TSI") rather than as a black-box score.

Full counterfactual do-calculus (DoWhy) is roadmap; this ships the two things a
clinician actually asks for at the bedside: which risk factors are ACTIVE for
this patient, and a plain-language narrative tying them to the verdict.

Edges point to `healing_rate` (a latent that drives `outcome`); a negative sign
means the factor slows healing (raises delayed/non-union risk).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.db.models import Patient, Scan

# ── The DAG: factor -> healing_rate, with sign, weight, citation ─────────────
# weight is a relative effect size in [0,1]; sign -1 slows healing.


@dataclass(frozen=True)
class CausalEdge:
    factor: str
    sign: int          # -1 slows healing, +1 speeds
    weight: float      # relative effect size
    citation: str


CAUSAL_DAG: tuple[CausalEdge, ...] = (
    CausalEdge("smoker", -1, 0.80, "Scolaro 2014 (JBJS): smoking ~2x nonunion risk"),
    CausalEdge("diabetic", -1, 0.65, "Jiao 2015: diabetes impairs callus, delays union"),
    CausalEdge("older_age", -1, 0.45, "Hak 2014: advanced age slows remodelling"),
    CausalEdge("comminuted", -1, 0.70, "Marquez-Lara 2016: comminution raises nonunion"),
    CausalEdge("open_high_energy", -1, 0.75, "Gustilo 1976; Antonova 2013: open/high-energy delays"),
    CausalEdge("late_week_low_tsi", -1, 0.85, "Tower 1993; Mattei 2021: low TSI late = poor stiffness"),
    CausalEdge("secondary_peak", -1, 0.90, "Implant-loosening resonance signature (hardware review)"),
)

# thresholds that decide whether a factor is "active" for this scan
_OLDER_AGE_YEARS = 55
_LATE_WEEK = 10.0
_LOW_TSI_SQ = 64.0          # squared-TSI full-weight-bearing threshold (services.tsi)
_LABEL_BY_LIGHT = {"green": "Stable", "amber": "Delayed Union", "red": "Non-Union"}


@dataclass(frozen=True)
class ActiveFactor:
    factor: str
    value: str
    sign: int
    weight: float
    citation: str


def _active_factors(patient: Patient, scan: Scan) -> list[ActiveFactor]:
    """Which DAG factors fire for this patient/scan, strongest first."""
    edges = {e.factor: e for e in CAUSAL_DAG}
    active: list[ActiveFactor] = []

    def add(factor: str, value: str) -> None:
        e = edges[factor]
        active.append(ActiveFactor(factor, value, e.sign, e.weight, e.citation))

    if patient.smoker:
        add("smoker", "yes")
    if patient.diabetic:
        add("diabetic", "yes")
    if patient.age >= _OLDER_AGE_YEARS:
        add("older_age", f"{patient.age} yr")
    if (patient.fracture_type or "").lower() == "comminuted":
        add("comminuted", patient.fracture_type)
    tsi = scan.tsi_pct
    if scan.week >= _LATE_WEEK and tsi is not None and tsi < _LOW_TSI_SQ:
        add("late_week_low_tsi", f"week {scan.week:g}, TSI {tsi:.0f}%")
    if scan.secondary_peak_hz:
        add("secondary_peak", f"{scan.secondary_peak_hz:.0f} Hz second peak")

    active.sort(key=lambda a: a.weight, reverse=True)
    return active


def explain_verdict(patient: Patient, scan: Scan, n_similar: int = 0) -> dict:
    """Causal explanation for a scan's verdict: active risk factors + narrative."""
    active = _active_factors(patient, scan)
    verdict = _LABEL_BY_LIGHT.get(scan.traffic_light or "", scan.predicted_label or "Unknown")

    if active:
        factor_phrases = [f"{a.factor.replace('_', ' ')} ({a.value})" for a in active[:3]]
        joined = " + ".join(factor_phrases)
        narrative = f"Flagged {verdict} because {joined}"
        if n_similar > 0:
            narrative += f", matching {n_similar} similar prior case(s)"
        narrative += "."
    else:
        narrative = (f"{verdict}: no adverse healing factors active — resonance and "
                     f"stiffness are consistent with normal union")
        if n_similar > 0:
            narrative += f" ({n_similar} similar prior case(s))"
        narrative += "."

    return {
        "verdict": verdict,
        "n_similar": n_similar,
        "active_factors": [
            {"factor": a.factor, "value": a.value, "sign": a.sign,
             "weight": a.weight, "citation": a.citation}
            for a in active
        ],
        "narrative": narrative,
    }
