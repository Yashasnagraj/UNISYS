"""
SQLModel tables for ResoScan. Arrays/JSON are stored as TEXT (SQLite has no
array type). The scans table is the central verdict record; tsi_std_raw vs
tsi_std_norm is the headline normalization-proof metric.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_code: str = Field(index=True, unique=True)
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
    status: Optional[str] = None  # cleared | delayed | non-union
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HealthyReference(SQLModel, table=True):
    __tablename__ = "healthy_references"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    bone: str = "Tibia"
    f_healthy_hz: float
    zeta_healthy: Optional[float] = None
    source: str = "profile"  # profile | device_calibration
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class Device(SQLModel, table=True):
    __tablename__ = "devices"

    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True, unique=True)
    port: Optional[str] = None
    baud: int = 115200
    fw_version: Optional[str] = None
    last_seen: Optional[datetime] = None


class CaptureSession(SQLModel, table=True):
    __tablename__ = "capture_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: Optional[int] = Field(default=None, foreign_key="patients.id")
    device_id: Optional[int] = Field(default=None, foreign_key="devices.id")
    source: str = "sim"  # sim | device | upload
    n_sweeps: int = 8
    norm_config_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Scan(SQLModel, table=True):
    __tablename__ = "scans"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    session_id: Optional[int] = Field(default=None, foreign_key="capture_sessions.id")
    scan_date: date
    week: float = 0.0
    source: str = "sim"  # sim | device | upload
    fs_hz: int = 4096

    # raw + normalized signal storage (base64 int16 or JSON float list)
    raw_samples_b64: Optional[str] = None
    norm_samples_b64: Optional[str] = None

    # headline measured values (post-normalization)
    f_peak_hz: Optional[float] = None
    f_healthy_hz: Optional[float] = None
    tsi_pct: Optional[float] = None          # canonical squared TSI
    tsi_pct_linear: Optional[float] = None   # legacy linear, for comparison
    zeta: Optional[float] = None
    q_factor: Optional[float] = None
    bandwidth_hz: Optional[float] = None
    mdf: Optional[float] = None
    secondary_peak_hz: Optional[float] = None

    # 25-feature vector + ML verdict (JSON TEXT)
    features_json: Optional[str] = None
    predicted_label: Optional[str] = None
    confidence: Optional[float] = None
    probabilities_json: Optional[str] = None
    model_name: Optional[str] = None

    # clinical classification
    traffic_light: Optional[str] = None      # green | amber | red
    recommendation: Optional[str] = None
    rust_score: Optional[int] = None

    # quality
    preload_n: Optional[float] = None
    quality_score: Optional[float] = None
    snr_db: Optional[float] = None
    saturated: bool = False

    # repeatability (the headline normalization metric)
    tsi_std_raw: Optional[float] = None
    tsi_std_norm: Optional[float] = None
    snr_gain_db: Optional[float] = None

    # normalization stage snapshots (JSON, for the normalization view)
    stages_json: Optional[str] = None
    norm_psd_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
