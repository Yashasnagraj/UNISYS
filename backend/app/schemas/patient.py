"""Pydantic response/request models for patients and their scans (camelCase out)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True,
                              from_attributes=True)


class ScanRead(CamelModel):
    id: int
    scan_date: date
    created_at: Optional[datetime] = None   # full timestamp for the history table
    week: float
    source: str
    f_peak_hz: Optional[float] = None
    f_healthy_hz: Optional[float] = None
    tsi_pct: Optional[float] = None
    tsi_pct_linear: Optional[float] = None
    zeta: Optional[float] = None
    q_factor: Optional[float] = None
    bandwidth_hz: Optional[float] = None
    snr_db: Optional[float] = None
    tsi_std_raw: Optional[float] = None
    tsi_std_norm: Optional[float] = None
    snr_gain_db: Optional[float] = None
    predicted_label: Optional[str] = None
    confidence: Optional[float] = None
    traffic_light: Optional[str] = None


class PatientCreate(CamelModel):
    name: str
    age: int
    sex: str = "M"
    smoker: bool = False
    diabetic: bool = False
    bmi: Optional[float] = None
    bone: str = "Tibia"
    fracture_type: str = "Transverse"
    fracture_date: date
    hospital: Optional[str] = None
    surgeon: Optional[str] = None
    patient_code: Optional[str] = None  # auto-generated if omitted


class PatientRead(CamelModel):
    id: int
    patient_code: str
    name: str
    age: int
    sex: str
    smoker: bool
    diabetic: bool
    bmi: Optional[float] = None
    bone: str
    fracture_type: str
    fracture_date: date
    hospital: Optional[str] = None
    surgeon: Optional[str] = None
    status: Optional[str] = None
    # summary of latest scan, for the rail
    latest_tsi: Optional[float] = None
    latest_week: Optional[float] = None
    scan_count: int = 0


class PatientDetail(PatientRead):
    scans: list[ScanRead] = []
