"""
Seed the 3 validated demo patients (Arjun / Priya / Vikram) and their dense
scan histories from ortho_simulator/data/demo_patients.py into SQLite.

Idempotent: only seeds when the patients table is empty.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.engine_bridge import DEMO_PATIENTS, BONE_PROFILES
from app.db.database import engine
from app.db.models import Outcome, Patient, HealthyReference, Scan
from app.services.tsi import compute_tsi_squared

# Device-domain resonance target per demo patient (f_healthy default 240 Hz):
# a healed leg rings near the healthy mode, a non-union rings low and dull.
# Used by the feature backfill so the knowledge graph has a coherent, single-
# domain cohort with confirmed outcomes to retrieve against.
# f_peak chosen so squared-TSI (f/240)^2*100 lands in the right traffic-light
# band: Stable >=64 (green), Delayed 30-64 (amber), Non-Union <30 (red).
_BACKFILL_PROFILE = {
    "P-2611": {"f_peak": 232.0, "label": "Stable",        "week": 12.0},  # TSI ~93
    "P-2742": {"f_peak": 180.0, "label": "Delayed Union", "week": 14.0},  # TSI ~56
    "P-2810": {"f_peak": 124.0, "label": "Non-Union",     "week": 16.0},  # TSI ~27
}
_BACKFILL_SCANS_PER_PATIENT = 3


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


def backfill_demo_features(force: bool = False) -> int:
    """Give each demo patient device-domain, feature-bearing scans plus a
    confirmed outcome, so the knowledge graph and retrain corpus have data.

    Generates a realistic capture batch per patient at a state-appropriate
    resonance, runs it through the SAME pipeline as a live scan, and records the
    known final outcome on the latest scan. Idempotent: skips if outcomes already
    exist (unless `force`). Returns the number of scans created.
    """
    from app.db.models import CaptureSession  # local import: avoid cycles
    from app.services.feedback import record_outcome
    from app.services.pipeline import device_norm_config, run_pipeline
    from app.services.sim_source import make_capture_batch

    created = 0
    with Session(engine) as session:
        if not force and session.exec(select(Outcome)).first() is not None:
            return 0

        for code, prof in _BACKFILL_PROFILE.items():
            patient = session.exec(
                select(Patient).where(Patient.patient_code == code)
            ).first()
            if not patient:
                continue

            last_scan = None
            for i in range(_BACKFILL_SCANS_PER_PATIENT):
                batch = make_capture_batch(
                    f_peak=prof["f_peak"], n_sweeps=24,
                    seed=(patient.id * 100 + i),
                )
                last_scan = run_pipeline(
                    sweeps=batch["sweeps"], fs=batch["fs"],
                    patient=patient, source="replay",
                    week=prof["week"] - (2 * (_BACKFILL_SCANS_PER_PATIENT - 1 - i)),
                    db=session,
                    norm_cfg=device_norm_config(len(batch["sweeps"]), batch["fs"]),
                )
                created += 1

            if last_scan is not None:
                record_outcome(
                    session, patient_id=patient.id, scan_id=last_scan.id,
                    true_label=prof["label"], weeks_to_walk=None, rust_16w=None,
                    source="clinician",
                )
    return created
