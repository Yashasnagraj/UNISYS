"""
The single ResoScan scan pipeline.

ALL three scan sources (sim | device | upload) converge here:

    sweeps + fs  →  normalize()  →  extract_features()  →  predict_healing_status()
                 →  tsi_squared()  →  classify_traffic_light()
                 →  repeatability()  →  persist Scan row  →  return Scan

This is the end-to-end proof: one code path, same math, regardless of whether
the signal came from a cheap ADXL345, a simulation, or an uploaded file.
"""
from __future__ import annotations

import base64
import json
from datetime import date
from typing import Optional

import numpy as np
from sqlmodel import Session, select

from app.db.models import CaptureSession, HealthyReference, Patient, Scan
from app.engine_bridge import (
    BONE_PROFILES, FS, extract_features, predict_healing_status,
)
from app.services.normalization import NormConfig, normalize, repeatability
from app.services.sim_source import make_cheap_sweeps
from app.services.tsi import (
    classify_traffic_light, compute_tsi_linear, compute_tsi_squared,
)


# ── Device-domain constants ──────────────────────────────────────────────────
# The ADXL345 samples at 800 Hz (Nyquist 400 Hz), so the tracked tibial mode is
# read in a low band — the sim engine's 300–850 Hz config would filter it out.
# This default healthy reference is calibrated empirically against real captures
# so a healthy-leg reading yields a sensible (high) TSI; a contralateral
# calibration scan overrides it per-patient (the honest method).
# Empirically, the device-tuned normalization extracts the tibial first bending
# mode at ~237 Hz on a healthy leg — matching the published in-vivo healthy value
# of ~240 Hz (Van der Perre & Lowet; skin-surface accelerometer studies). We use
# that literature value as the default healthy reference; a contralateral
# calibration scan overrides it per-patient.
DEVICE_F_HEALTHY_DEFAULT = 240.0   # Hz — healthy tibia first bending mode [VanderPerre]


def device_norm_config(n_sweeps: int) -> NormConfig:
    """NormConfig tuned for the 800 Hz device: keep the 30–390 Hz band where the
    tracked tibial mode lives, Welch nfft sized for ~800-sample sweeps."""
    return NormConfig(
        n_sweeps=n_sweeps,
        band_low_hz=30.0, band_high_hz=390.0,
        peak_lo_hz=30.0, peak_hi_hz=390.0,
        welch_nfft=512, bp_order=4,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_f_healthy(patient: Patient, db: Session, source: str = "sim") -> float:
    """Look up the patient's healthy reference frequency.

    Device scans live in a different frequency domain, so they prefer a stored
    device-calibration reading and fall back to the device default — never the
    sim bone-profile (850 Hz), which would make a real device TSI meaningless.
    """
    refs = list(db.exec(
        select(HealthyReference)
        .where(HealthyReference.patient_id == patient.id)
        .order_by(HealthyReference.captured_at.desc())
    ))
    if source == "device":
        for r in refs:
            if r.source == "device_calibration":
                return float(r.f_healthy_hz)
        return DEVICE_F_HEALTHY_DEFAULT
    # sim / upload: prefer any device-calibration, else profile, else bone default
    if refs:
        for r in refs:
            if r.source == "device_calibration":
                return float(r.f_healthy_hz)
        return float(refs[0].f_healthy_hz)
    return float(BONE_PROFILES.get(patient.bone, {}).get("f_healthy", 850.0))


def _encode_signal(sig: np.ndarray) -> str:
    """Encode a float32 array as base64 for storage."""
    return base64.b64encode(sig.astype(np.float32).tobytes()).decode("ascii")


def _psd_to_json(freqs: np.ndarray, psd_db: np.ndarray, n: int = 512) -> str:
    """Downsample and serialise PSD arrays for storage."""
    if len(freqs) <= n:
        return json.dumps({"freqs": freqs.tolist(), "psd_db": psd_db.tolist()})
    idx = np.linspace(0, len(freqs) - 1, n).astype(int)
    return json.dumps({"freqs": freqs[idx].tolist(), "psd_db": psd_db[idx].tolist()})


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    sweeps: list[np.ndarray],
    fs: float,
    patient: Patient,
    source: str,
    week: float,
    db: Session,
    norm_cfg: Optional[NormConfig] = None,
) -> Scan:
    """Run the full pipeline and persist a Scan row. Returns the saved Scan."""
    cfg = norm_cfg or NormConfig(n_sweeps=len(sweeps))
    f_healthy = _get_f_healthy(patient, db, source=source)

    # 1. Normalize
    norm_result = normalize(sweeps, fs, cfg)

    # 2. Repeatability (the headline metric)
    rep = repeatability(sweeps, fs, f_healthy, cfg)

    # 3. Feature extraction on the normalized signal
    feats = extract_features(
        signal=norm_result.normalized_signal,
        fs=int(fs),
        f_healthy=f_healthy,
        callus_pct=0.0,   # unknown at inference time; callus_proxy derived from f_peak
    )

    # 4. ML classification
    ml = predict_healing_status(
        signal=norm_result.normalized_signal,
        fs=int(fs),
        f_healthy=f_healthy,
        callus_pct=0.0,
    )

    # 5. TSI (canonical squared + legacy linear)
    f_peak = norm_result.f_peak_hz
    tsi_sq  = compute_tsi_squared(f_peak, f_healthy)
    tsi_lin = compute_tsi_linear(f_peak, f_healthy)

    # 6. Clinical classification
    has_secondary = bool(feats.get("peak_splitting_flag", 0))
    tl = classify_traffic_light(
        tsi_sq, zeta=norm_result.zeta, week=week, has_secondary=has_secondary
    )

    # 7. Serialise stage snapshots and PSD for the normalization view
    stages_json = json.dumps([
        {"name": s.name, "note": s.note, "signal": s.signal}
        for s in norm_result.stages
    ])
    norm_psd_json = _psd_to_json(norm_result.freqs, norm_result.psd_db)

    # 8. Build capture session
    cap_session = CaptureSession(
        patient_id=patient.id, source=source,
        n_sweeps=len(sweeps),
        norm_config_json=json.dumps(cfg.to_dict()),
    )
    db.add(cap_session)
    db.flush()  # get id without committing

    # 9. Persist scan
    improvement = (
        round(rep.tsi_std_raw / rep.tsi_std_norm, 2)
        if rep.tsi_std_norm > 1e-9 else None
    )
    scan = Scan(
        patient_id=patient.id,
        session_id=cap_session.id,
        scan_date=date.today(),
        week=week,
        source=source,
        fs_hz=int(fs),
        raw_samples_b64=_encode_signal(np.asarray(sweeps[0])),
        norm_samples_b64=_encode_signal(norm_result.normalized_signal),
        f_peak_hz=round(f_peak, 3),
        f_healthy_hz=round(f_healthy, 3),
        tsi_pct=round(tsi_sq, 3),
        tsi_pct_linear=round(tsi_lin, 3),
        zeta=round(norm_result.zeta, 5) if norm_result.zeta else None,
        q_factor=round(norm_result.q_factor, 3) if norm_result.q_factor else None,
        bandwidth_hz=round(norm_result.bandwidth_hz, 3) if norm_result.bandwidth_hz else None,
        features_json=json.dumps({k: round(float(v), 6) for k, v in feats.items()}),
        predicted_label=ml.get("predicted_label"),
        confidence=round(float(ml.get("confidence", 0.0)), 2),
        probabilities_json=json.dumps(ml.get("probabilities", {})),
        model_name=ml.get("model_name"),
        traffic_light=tl["traffic_light"],
        recommendation=tl["recommendation"],
        snr_db=round(norm_result.snr_db_norm, 2),
        tsi_std_raw=rep.tsi_std_raw,
        tsi_std_norm=rep.tsi_std_norm,
        snr_gain_db=rep.snr_gain_db,
        stages_json=stages_json,
        norm_psd_json=norm_psd_json,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Update patient status from traffic light
    status_map = {"green": "cleared", "amber": "delayed", "red": "non-union"}
    patient.status = status_map.get(tl["traffic_light"], patient.status)
    db.add(patient)
    db.commit()

    return scan


# ── Source-specific entry points ──────────────────────────────────────────────

def run_sim_scan(
    patient: Patient,
    db: Session,
    week: float = 0.0,
    callus_pct: float = 60.0,
    n_sweeps: int = 8,
) -> Scan:
    data = make_cheap_sweeps(
        callus_pct=callus_pct,
        f_healthy=_get_f_healthy(patient, db),
        n_sweeps=n_sweeps,
        seed=int(patient.id * 17 + round(week * 3)),
    )
    return run_pipeline(
        sweeps=data["sweeps"], fs=data["fs"],
        patient=patient, source="sim", week=week, db=db,
        norm_cfg=NormConfig(n_sweeps=n_sweeps),
    )


def run_upload_scan(
    patient: Patient,
    db: Session,
    samples: list[float],
    fs: int = 4096,
    week: float = 0.0,
) -> Scan:
    sweeps = [np.asarray(samples, dtype=float)]
    return run_pipeline(
        sweeps=sweeps, fs=float(fs),
        patient=patient, source="upload", week=week, db=db,
        norm_cfg=NormConfig(n_sweeps=1),
    )


def run_device_scan(
    patient: Patient,
    db: Session,
    week: float = 0.0,
    n_sweeps: int = 8,
    port: Optional[str] = None,
    baud: int = 115200,
) -> Scan:
    from app.services.device_ingest import capture_sweeps  # lazy import
    # Each device sweep is its own fresh boot (~6 s), so cap the count to keep a
    # live scan reasonably short while still giving the normalizer ≥2-3 sweeps.
    dev_sweeps = min(n_sweeps, 3)
    data = capture_sweeps(n_sweeps=dev_sweeps, port=port, baud=baud)
    sweeps = data["sweeps"]
    return run_pipeline(
        sweeps=sweeps, fs=data["fs"],
        patient=patient, source="device", week=week, db=db,
        norm_cfg=device_norm_config(len(sweeps)),
    )


def run_device_calibration(
    patient: Patient,
    db: Session,
    n_sweeps: int = 6,
    port: Optional[str] = None,
    baud: int = 115200,
) -> dict:
    """Capture the patient's HEALTHY (contralateral) limb and store its resonant
    frequency as the device-domain f_healthy reference. Subsequent device scans
    compute TSI relative to this — the clinically correct contralateral method.
    Returns {'f_healthy_hz', 'n_sweeps'}."""
    from app.services.device_ingest import capture_sweeps  # lazy import
    data = capture_sweeps(n_sweeps=n_sweeps, port=port, baud=baud)
    sweeps = data["sweeps"]
    cfg = device_norm_config(len(sweeps))
    res = normalize(sweeps, data["fs"], cfg)
    f_healthy = float(res.f_peak_hz)

    db.add(HealthyReference(
        patient_id=patient.id, bone=patient.bone,
        f_healthy_hz=f_healthy,
        zeta_healthy=float(res.zeta) if res.zeta else None,
        source="device_calibration",
    ))
    db.commit()
    return {"f_healthy_hz": round(f_healthy, 2), "n_sweeps": len(sweeps)}
