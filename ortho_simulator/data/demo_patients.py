"""
Demo patient profiles with realistic scan histories.

Each patient has:
  - Demographics (age, sex, smoker, diabetic, BMI)
  - Fracture metadata (bone, fracture type, date)
  - A scan history: list of (date, weeks_since_fracture, f_n_hz, tsi_pct,
    zeta, classification)

The TSI trajectories are sampled along a Gompertz curve with biological
noise so the personalised fit produces a slightly different curve than the
population average — exactly what the demo wants to showcase.
"""

from datetime import date, timedelta
from typing import List, Dict


# Today reference — set explicitly so demo behaviour is reproducible across
# machines and time zones. Override at call time if needed.
TODAY = date(2026, 5, 20)


def _scan(d: date, w: float, f_n: float, tsi: float, zeta: float,
          classification: str) -> Dict:
    return {
        "date": d, "week": w, "f_n_hz": f_n, "tsi_pct": tsi,
        "zeta": zeta, "classification": classification,
    }


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
        "fracture_date": TODAY - timedelta(weeks=8, days=2),
        "hospital": "Ramaiah Memorial Hospital",
        "surgeon": "Dr. R. Krishnan",
        "scans": [
            _scan(TODAY - timedelta(weeks=8), 0.3, 320.0, 14.2, 0.180, "Non-Union"),
            _scan(TODAY - timedelta(weeks=6), 2.3, 410.0, 23.3, 0.140, "Non-Union"),
            _scan(TODAY - timedelta(weeks=4), 4.3, 575.0, 45.8, 0.085, "Delayed Union"),
            _scan(TODAY - timedelta(weeks=2), 6.3, 695.0, 66.8, 0.045, "Delayed Union"),
            _scan(TODAY,                       8.3, 770.0, 82.1, 0.030, "Stable"),
        ],
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
        "fracture_date": TODAY - timedelta(weeks=10),
        "hospital": "Ramaiah Memorial Hospital",
        "surgeon": "Dr. S. Patel",
        "scans": [
            _scan(TODAY - timedelta(weeks=10), 0.0, 310.0, 13.3, 0.190, "Non-Union"),
            _scan(TODAY - timedelta(weeks=8),  2.0, 360.0, 17.9, 0.165, "Non-Union"),
            _scan(TODAY - timedelta(weeks=6),  4.0, 440.0, 26.8, 0.130, "Non-Union"),
            _scan(TODAY - timedelta(weeks=4),  6.0, 525.0, 38.2, 0.095, "Delayed Union"),
            _scan(TODAY - timedelta(weeks=2),  8.0, 595.0, 49.0, 0.075, "Delayed Union"),
            _scan(TODAY,                       10.0, 650.0, 58.5, 0.058, "Delayed Union"),
        ],
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
        "fracture_date": TODAY - timedelta(weeks=12),
        "hospital": "Ramaiah Memorial Hospital",
        "surgeon": "Dr. R. Krishnan",
        "scans": [
            _scan(TODAY - timedelta(weeks=12), 0.0, 305.0, 12.9, 0.195, "Non-Union"),
            _scan(TODAY - timedelta(weeks=10), 2.0, 330.0, 15.1, 0.175, "Non-Union"),
            _scan(TODAY - timedelta(weeks=8),  4.0, 360.0, 17.9, 0.160, "Non-Union"),
            _scan(TODAY - timedelta(weeks=6),  6.0, 390.0, 21.0, 0.150, "Non-Union"),
            _scan(TODAY - timedelta(weeks=4),  8.0, 410.0, 23.3, 0.143, "Non-Union"),
            _scan(TODAY - timedelta(weeks=2),  10.0, 425.0, 25.0, 0.138, "Non-Union"),
            _scan(TODAY,                       12.0, 440.0, 26.8, 0.135, "Non-Union"),
        ],
    },
}


def get_patient_names() -> List[str]:
    return list(DEMO_PATIENTS.keys())


def get_patient(name: str) -> Dict:
    return DEMO_PATIENTS[name]
