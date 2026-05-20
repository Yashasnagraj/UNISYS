"""
Demo patient profiles with realistic, dense scan histories.

Each patient has:
  - Demographics (age, sex, smoker, diabetic, BMI)
  - Fracture metadata (bone, fracture type, date)
  - A dense scan history covering the FULL healing journey:
      * twice-weekly scans through the first month
      * weekly scans afterwards
    Values follow a personalised Gompertz trajectory with biologically
    plausible measurement noise so the curve fit produces a curve the demo
    can visibly differentiate from the population average.
"""

from datetime import date, timedelta
from typing import Dict, List

import numpy as np


# Today reference — set explicitly so demo behaviour is reproducible.
TODAY = date(2026, 5, 20)

# Healthy-tibia reference for f_n conversion. Matches engine/data/bone_profiles.
F_HEALTHY_HZ = 850.0
F_BASELINE_HZ = 300.0      # f_n at week 0 (fresh fracture)
TSI_TO_FN_RANGE = F_HEALTHY_HZ - F_BASELINE_HZ


def _gompertz(t_weeks: float, k: float, t0: float) -> float:
    """TSI percentage at time t given Gompertz params."""
    return 100.0 * float(np.exp(-np.exp(-k * (t_weeks - t0))))


def _classify(tsi: float) -> str:
    if tsi >= 75: return "Stable"
    if tsi >= 40: return "Delayed Union"
    return "Non-Union"


def _zeta_from_tsi(tsi: float) -> float:
    """Damping ratio decreases as bone stiffens. Matches engine.signal_generator."""
    # zeta ~ 0.20 at TSI=0, ~0.025 at TSI=100, smooth interpolation
    return float(0.20 - 0.175 * (tsi / 100.0) ** 1.3)


def _fn_from_tsi(tsi: float) -> float:
    """f_n in Hz from TSI percentage."""
    return F_BASELINE_HZ + TSI_TO_FN_RANGE * (tsi / 100.0)


def _generate_scans(
    fracture_date: date,
    weeks_observed: float,
    k: float,
    t0: float,
    noise_pct: float,
    seed: int,
    early_cadence_days: int = 3,
    late_cadence_days: int = 7,
    early_window_weeks: float = 4.0,
) -> List[Dict]:
    """Generate a sequence of scans along a Gompertz curve.

    Twice-weekly cadence through `early_window_weeks` (the rapid-change
    phase), then weekly thereafter. Adds Gaussian noise on TSI to make the
    series look like real device readings.
    """
    rng = np.random.RandomState(seed)
    scans: List[Dict] = []

    days_total = int(weeks_observed * 7)
    early_days = int(early_window_weeks * 7)

    days = []
    d = 0
    while d <= days_total:
        days.append(d)
        d += early_cadence_days if d < early_days else late_cadence_days

    # Always include the final "today" scan
    if days[-1] != days_total:
        days.append(days_total)

    for d_idx, day in enumerate(days):
        w = day / 7.0
        tsi_clean = _gompertz(w, k, t0)
        # Bigger relative noise at low TSI (signal noisier on a soft callus)
        sigma = noise_pct * (1.0 + 0.5 * (1.0 - tsi_clean / 100.0))
        tsi_noisy = float(np.clip(tsi_clean + rng.normal(0, sigma), 0.5, 99.9))
        scans.append({
            "date": fracture_date + timedelta(days=day),
            "week": round(w, 2),
            "f_n_hz": round(_fn_from_tsi(tsi_noisy), 1),
            "tsi_pct": round(tsi_noisy, 1),
            "zeta": round(_zeta_from_tsi(tsi_noisy), 3),
            "classification": _classify(tsi_noisy),
        })
    return scans


# ============================================================================
#  Patient registry
# ============================================================================

_arjun_frac = TODAY - timedelta(weeks=8, days=2)
_priya_frac = TODAY - timedelta(weeks=10)
_vikram_frac = TODAY - timedelta(weeks=12)


DEMO_PATIENTS: Dict[str, Dict] = {
    "P-2611 — Arjun Mehta (healing on pace)": {
        "name": "Arjun Mehta",
        "patient_id": "P-2611",
        "age": 28,
        "sex": "M",
        "smoker": False,
        "diabetic": False,
        "bmi": 24.1,
        "bone": "Tibia",
        "fracture_type": "Transverse",
        "fracture_date": _arjun_frac,
        "hospital": "Ramaiah Memorial Hospital",
        "surgeon": "Dr. R. Krishnan",
        # Healthy young adult: faster k, earlier inflection
        "scans": _generate_scans(
            fracture_date=_arjun_frac,
            weeks_observed=(TODAY - _arjun_frac).days / 7.0,
            k=0.48, t0=4.0, noise_pct=2.2, seed=11,
        ),
    },
    "P-2742 — Priya Iyer (slower, smoker)": {
        "name": "Priya Iyer",
        "patient_id": "P-2742",
        "age": 45,
        "sex": "F",
        "smoker": True,
        "diabetic": False,
        "bmi": 27.8,
        "bone": "Tibia",
        "fracture_type": "Oblique",
        "fracture_date": _priya_frac,
        "hospital": "Ramaiah Memorial Hospital",
        "surgeon": "Dr. S. Patel",
        # Smoker -> 30% slower union, delayed inflection
        "scans": _generate_scans(
            fracture_date=_priya_frac,
            weeks_observed=(TODAY - _priya_frac).days / 7.0,
            k=0.30, t0=6.5, noise_pct=2.5, seed=27,
        ),
    },
    "P-2810 — Vikram Singh (non-union concern)": {
        "name": "Vikram Singh",
        "patient_id": "P-2810",
        "age": 67,
        "sex": "M",
        "smoker": True,
        "diabetic": True,
        "bmi": 30.2,
        "bone": "Tibia",
        "fracture_type": "Comminuted",
        "fracture_date": _vikram_frac,
        "hospital": "Ramaiah Memorial Hospital",
        "surgeon": "Dr. R. Krishnan",
        # Smoker + diabetic + elderly: severely impaired union, curve stalls
        # well below the weight-bearing threshold trajectory.
        "scans": _generate_scans(
            fracture_date=_vikram_frac,
            weeks_observed=(TODAY - _vikram_frac).days / 7.0,
            k=0.06, t0=18.0, noise_pct=1.4, seed=42,
        ),
    },
}


def get_patient_names() -> List[str]:
    return list(DEMO_PATIENTS.keys())


def get_patient(name: str) -> Dict:
    return DEMO_PATIENTS[name]
