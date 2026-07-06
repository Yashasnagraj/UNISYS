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


class RawSweepSet(SQLModel, table=True):
    """All N raw sweeps of one capture, stored losslessly so a real capture can
    be replayed through the pipeline later. `sweeps_b64` is a base64 float32
    blob of a (n_sweeps, n_samples) array. Additive table — created by
    create_all; the Scan row keeps storing only the first sweep for quick reads.
    """
    __tablename__ = "raw_sweep_sets"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="capture_sessions.id", index=True)
    fs_hz: float
    n_sweeps: int
    n_samples: int
    sweeps_b64: str  # base64(float32 (n_sweeps, n_samples))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClinicianFeedback(SQLModel, table=True):
    """A clinician's agree/override on a scan's ML verdict. `override_label` (when
    set) is one of the four LABEL_NAMES. These feed the retrain corpus alongside
    confirmed outcomes. Additive table."""
    __tablename__ = "clinician_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scans.id", index=True)
    clinician: Optional[str] = None
    agree: bool = True
    override_label: Optional[str] = None   # one of LABEL_NAMES when disagreeing
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Outcome(SQLModel, table=True):
    """Ground-truth healing outcome for a patient/scan, confirmed by a clinician
    (or a later follow-up). `true_label` is one of the four LABEL_NAMES. This is
    the target the single-scan classifier learns from. Additive table."""
    __tablename__ = "outcomes"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    scan_id: Optional[int] = Field(default=None, foreign_key="scans.id", index=True)
    true_label: str                        # one of LABEL_NAMES
    weeks_to_walk: Optional[float] = None
    rust_16w: Optional[int] = None
    source: str = "clinician"              # clinician | followup | synthetic
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModelVersion(SQLModel, table=True):
    """One trained version of the single-scan classifier. `macro_f1_holdout` and
    `champion_f1` are both scored on the SAME frozen holdout, so promotion
    (`promoted`) is an honest apples-to-apples comparison. `is_active` marks the
    bundle currently copied to the live model path. Additive table."""
    __tablename__ = "model_versions"

    id: Optional[int] = Field(default=None, primary_key=True)
    version: int = Field(index=True)
    path: str                              # versions/model_v{N}.pkl
    synthetic_n: int = 0
    clinician_pairs: int = 0
    macro_f1_holdout: float = 0.0          # this version, on the frozen holdout
    champion_f1: Optional[float] = None    # prior champion, same holdout (None for v1)
    promoted: bool = False                 # did it beat/tie the champion?
    is_active: bool = False                # currently the live model
    notes: Optional[str] = None
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
