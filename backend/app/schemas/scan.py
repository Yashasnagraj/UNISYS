"""Request / response schemas for scans and the device endpoint."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Optional, Union

from pydantic import Field

from app.schemas.patient import CamelModel


# ── POST /scans — tagged union on 'source' ──────────────────────────────────

class SimScanRequest(CamelModel):
    source: Literal["sim"] = "sim"
    patient_id: int
    week: float = 0.0
    callus_pct: float = 60.0   # 0-100, how healed (0=fresh fracture, 100=full)
    n_sweeps: int = 8


class DeviceScanRequest(CamelModel):
    source: Literal["device"] = "device"
    patient_id: int
    week: float = 0.0
    n_sweeps: int = 8
    port: Optional[str] = None  # None → auto-detect CP2102


class UploadScanRequest(CamelModel):
    source: Literal["upload"] = "upload"
    patient_id: int
    week: float = 0.0
    samples: list[float]        # raw g-values, single sweep
    fs: int = 4096


ScanRequest = Annotated[
    Union[SimScanRequest, DeviceScanRequest, UploadScanRequest],
    Field(discriminator="source"),
]


# ── Per-stage snapshot (normalization view) ──────────────────────────────────

class StageSnapshotOut(CamelModel):
    name: str
    note: str
    signal: list[float]


# ── GET /scans/{id} ──────────────────────────────────────────────────────────

class ScanDetail(CamelModel):
    id: int
    patient_id: int
    scan_date: date
    week: float
    source: str
    f_peak_hz: Optional[float] = None
    f_healthy_hz: Optional[float] = None
    tsi_pct: Optional[float] = None
    tsi_pct_linear: Optional[float] = None
    zeta: Optional[float] = None
    q_factor: Optional[float] = None
    bandwidth_hz: Optional[float] = None
    predicted_label: Optional[str] = None
    confidence: Optional[float] = None
    traffic_light: Optional[str] = None
    recommendation: Optional[str] = None
    snr_db: Optional[float] = None
    snr_gain_db: Optional[float] = None
    tsi_std_raw: Optional[float] = None
    tsi_std_norm: Optional[float] = None
    improvement_factor: Optional[float] = None  # tsi_std_raw / tsi_std_norm


# ── GET /scans/{id}/normalization ────────────────────────────────────────────

class NormalizationDetail(CamelModel):
    scan_id: int
    stages: list[StageSnapshotOut]
    freqs: list[float]
    psd_db: list[float]
    f_peak_hz: float
    snr_db_raw: float
    snr_db_norm: float
    snr_gain_db: float


# ── GET /scans/{id}/repeatability ────────────────────────────────────────────

class RepeatabilityDetail(CamelModel):
    scan_id: int
    n_sweeps: int
    f_healthy_hz: float
    tsi_raw_per_sweep: list[float]
    tsi_norm_per_sweep: list[float]
    tsi_std_raw: float
    tsi_std_norm: float
    tsi_cv_raw: float
    tsi_cv_norm: float
    improvement_factor: float
    snr_gain_db: float


# ── GET /device/status ───────────────────────────────────────────────────────

class DeviceStatus(CamelModel):
    connected: bool
    port: Optional[str] = None
    baud: int = 115200
    description: str = ""
