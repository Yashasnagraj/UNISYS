"""
Seed the 3 validated demo patients (Arjun / Priya / Vikram) and their dense
scan histories from ortho_simulator/data/demo_patients.py into SQLite.

Idempotent: only seeds when the patients table is empty.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.engine_bridge import DEMO_PATIENTS, BONE_PROFILES
from app.db.database import engine
from app.db.models import Patient, HealthyReference, Scan
from app.services.tsi import compute_tsi_squared


def _status_for(final_label: str) -> str:
    return {
        "Stable": "cleared",
        "Delayed Union": "delayed",
        "Non-Union": "non-union",
    }.get(final_label, "delayed")


def seed_demo_patients() -> int:
    """Returns the number of patients seeded (0 if already present)."""
    with Session(engine) as session:
        existing = session.exec(select(Patient)).first()
        if existing is not None:
            return 0

        seeded = 0
        for _key, p in DEMO_PATIENTS.items():
            bone = p.get("bone", "Tibia")
            f_healthy = float(BONE_PROFILES.get(bone, {}).get("f_healthy", 850.0))
            scans = p.get("scans", [])
            final_label = scans[-1]["classification"] if scans else "Delayed Union"

            patient = Patient(
                patient_code=p["patient_id"],
                name=p["name"],
                age=p["age"],
                sex=p["sex"],
                smoker=p["smoker"],
                diabetic=p["diabetic"],
                bmi=p.get("bmi"),
                bone=bone,
                fracture_type=p["fracture_type"],
                fracture_date=p["fracture_date"],
                hospital=p.get("hospital"),
                surgeon=p.get("surgeon"),
                status=_status_for(final_label),
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)

            session.add(HealthyReference(
                patient_id=patient.id, bone=bone,
                f_healthy_hz=f_healthy,
                zeta_healthy=float(BONE_PROFILES.get(bone, {}).get("zeta_healthy", 0.025)),
                source="profile",
            ))

            for s in scans:
                f_n = float(s["f_n_hz"])
                session.add(Scan(
                    patient_id=patient.id,
                    scan_date=s["date"],
                    week=float(s["week"]),
                    source="sim",
                    fs_hz=4096,
                    f_peak_hz=f_n,
                    f_healthy_hz=f_healthy,
                    tsi_pct=compute_tsi_squared(f_n, f_healthy),
                    tsi_pct_linear=float(s["tsi_pct"]),
                    zeta=float(s["zeta"]),
                    predicted_label=s["classification"],
                    traffic_light={
                        "Stable": "green", "Delayed Union": "amber",
                        "Non-Union": "red",
                    }.get(s["classification"], "amber"),
                ))
            session.commit()
            seeded += 1
        return seeded
