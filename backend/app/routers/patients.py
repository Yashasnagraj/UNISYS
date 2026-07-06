"""Patient CRUD + detail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import Patient, Scan, HealthyReference
from app.engine_bridge import BONE_PROFILES
from app.schemas.patient import (
    PatientCreate, PatientRead, PatientDetail, ScanRead,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _scans_for(session: Session, patient_id: int) -> list[Scan]:
    # Order by (date, id) so the newest scan is truly last — scan_date is a DATE,
    # so same-day scans tie; id is monotonic creation order and breaks the tie.
    return list(session.exec(
        select(Scan).where(Scan.patient_id == patient_id)
        .order_by(Scan.scan_date, Scan.id)
    ))


def _to_read(session: Session, p: Patient) -> PatientRead:
    scans = _scans_for(session, p.id)
    latest = scans[-1] if scans else None
    return PatientRead(
        id=p.id, patient_code=p.patient_code, name=p.name, age=p.age, sex=p.sex,
        smoker=p.smoker, diabetic=p.diabetic, bmi=p.bmi, bone=p.bone,
        fracture_type=p.fracture_type, fracture_date=p.fracture_date,
        hospital=p.hospital, surgeon=p.surgeon, status=p.status,
        latest_tsi=(latest.tsi_pct if latest else None),
        latest_week=(latest.week if latest else None),
        scan_count=len(scans),
    )


@router.get("", response_model=list[PatientRead])
def list_patients(session: Session = Depends(get_session)):
    patients = session.exec(select(Patient).order_by(Patient.id)).all()
    return [_to_read(session, p) for p in patients]


@router.post("", response_model=PatientRead, status_code=201)
def create_patient(body: PatientCreate, session: Session = Depends(get_session)):
    code = body.patient_code
    if not code:
        n = len(session.exec(select(Patient)).all()) + 1
        code = f"P-{2900 + n}"
    if session.exec(select(Patient).where(Patient.patient_code == code)).first():
        raise HTTPException(409, f"patient_code {code} already exists")

    p = Patient(
        patient_code=code, name=body.name, age=body.age, sex=body.sex,
        smoker=body.smoker, diabetic=body.diabetic, bmi=body.bmi, bone=body.bone,
        fracture_type=body.fracture_type, fracture_date=body.fracture_date,
        hospital=body.hospital, surgeon=body.surgeon, status="delayed",
    )
    session.add(p)
    session.commit()
    session.refresh(p)

    # seed a healthy reference from the bone profile
    f_healthy = float(BONE_PROFILES.get(body.bone, {}).get("f_healthy", 850.0))
    session.add(HealthyReference(
        patient_id=p.id, bone=body.bone, f_healthy_hz=f_healthy,
        zeta_healthy=float(BONE_PROFILES.get(body.bone, {}).get("zeta_healthy", 0.025)),
        source="profile",
    ))
    session.commit()
    return _to_read(session, p)


def _resolve(session: Session, code: str) -> Patient:
    p = session.exec(select(Patient).where(Patient.patient_code == code)).first()
    if not p:
        # also allow numeric id
        if code.isdigit():
            p = session.get(Patient, int(code))
    if not p:
        raise HTTPException(404, f"patient {code} not found")
    return p


@router.get("/{code}", response_model=PatientDetail)
def get_patient(code: str, session: Session = Depends(get_session)):
    p = _resolve(session, code)
    base = _to_read(session, p)
    scans = [ScanRead.model_validate(s) for s in _scans_for(session, p.id)]
    return PatientDetail(**base.model_dump(), scans=scans)
