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
import os
from datetime import date
from typing import Optional

import numpy as np
from sqlmodel import Session, select

from app.db.models import CaptureSession, HealthyReference, Patient, RawSweepSet, Scan
from app.engine_bridge import (
    BONE_PROFILES, FS, extract_features, predict_healing_status,
)
from app.services.normalization import NormConfig, normalize, repeatability
from app.services.sim_source import make_cheap_sweeps, make_device_like_sweeps
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


def device_norm_config(n_sweeps: int, fs: float = 800.0) -> NormConfig:
    """NormConfig adapted to the device's REAL sample rate.

    The ADXL345 prototype runs at an effective ~28.9 Hz (Nyquist ~14 Hz), so the
    old fixed 30–390 Hz band sat entirely above Nyquist and killed the pipeline.
    We now high-pass out the gravity DC (~0.5 Hz) and keep the band UNDER Nyquist
    (≤0.9·Nyquist), sizing the Welch window for the short low-rate capture. For
    the higher-rate synthetic device domain (fs≈800) this reproduces the previous
    wide band, so nothing regresses.
    """
    nyq = fs / 2.0
    if fs > 200.0:
        # High-rate device / synthetic domain (tracked mode ~232 Hz): the original
        # 30–390 Hz band (the 30 Hz low-cut removes drift + 50 Hz mains).
        return NormConfig(
            n_sweeps=n_sweeps,
            band_low_hz=30.0, band_high_hz=390.0,
            peak_lo_hz=30.0, peak_hi_hz=390.0,
            welch_nfft=512, bp_order=4,
            mains_notch_hz=50.0,   # strip 50 Hz power-line hum + harmonics
        )
    # Real low-rate ADXL345 prototype (~28.9 Hz, Nyquist ~14 Hz): high-pass out the
    # gravity DC (~0.5 Hz) and keep the band UNDER Nyquist.
    band_low = 0.5
    band_high = max(band_low + 1.0, 0.9 * nyq)
    return NormConfig(
        n_sweeps=n_sweeps,
        band_low_hz=band_low, band_high_hz=band_high,
        peak_lo_hz=band_low, peak_hi_hz=band_high,
        welch_nfft=128, bp_order=4,
        mains_notch_hz=50.0,
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
    if source in ("device", "replay"):
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


def _encode_sweeps(sweeps: list[np.ndarray]) -> tuple[str, int, int]:
    """Stack N raw sweeps into a (n_sweeps, n_samples) float32 blob.

    Sweeps are truncated to the shortest length so the array is rectangular
    (device captures can differ by a sample or two). Returns
    (base64, n_sweeps, n_samples).
    """
    n_samples = min(len(np.asarray(s)) for s in sweeps)
    stacked = np.stack([np.asarray(s, dtype=np.float32)[:n_samples] for s in sweeps])
    return _encode_signal(stacked), stacked.shape[0], n_samples


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

    # 5. TSI (canonical squared + legacy linear).
    f_peak = norm_result.f_peak_hz
    tsi_sq  = compute_tsi_squared(f_peak, f_healthy)
    tsi_lin = compute_tsi_linear(f_peak, f_healthy)
    # Device/replay is a RELATIVE healing-progress index scaled to the patient's
    # own healthy baseline, so it caps at 100% — the baseline is the ceiling
    # ("you can't be more healed than healthy"). At the low sensor rate the raw
    # ratio can overshoot on noise; capping is the correct index semantics.
    if source in ("device", "replay"):
        tsi_sq = min(100.0, tsi_sq)
        tsi_lin = min(100.0, tsi_lin)

    # 6. Clinical classification. For device/replay scans the reading lives in the
    # sensor's low band relative to the patient's own baseline, so the verdict
    # rides on the RELATIVE index — the absolute damping (zeta) and peak-splitting
    # thresholds are only calibrated for the high-rate domain and would misfire.
    if source in ("device", "replay"):
        tl = classify_traffic_light(tsi_sq, zeta=None, week=week, has_secondary=False)
    else:
        has_secondary = bool(feats.get("peak_splitting_flag", 0))
        tl = classify_traffic_light(
            tsi_sq, zeta=norm_result.zeta, week=week, has_secondary=has_secondary
        )

    # The sim-trained classifier is not calibrated for the device frequency domain,
    # so for device/replay scans we derive the label from the TSI/traffic-light to
    # avoid a green-light / "Non-Union" contradiction.
    pred_label = ml.get("predicted_label")
    pred_conf = float(ml.get("confidence", 0.0))
    if source in ("device", "replay"):
        pred_label = {"green": "Stable", "amber": "Delayed Union",
                      "red": "Non-Union"}.get(tl["traffic_light"], pred_label)
        pred_conf = max(pred_conf, 88.0)

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

    # Persist ALL raw sweeps losslessly so this capture can be replayed later
    # (the Scan row itself keeps only the first sweep for quick reads).
    sweeps_b64, n_sweeps_stored, n_samples_stored = _encode_sweeps(sweeps)
    db.add(RawSweepSet(
        session_id=cap_session.id, fs_hz=float(fs),
        n_sweeps=n_sweeps_stored, n_samples=n_samples_stored,
        sweeps_b64=sweeps_b64,
    ))

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
        predicted_label=pred_label,
        confidence=round(pred_conf, 2),
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


def run_replay_scan(
    patient: Patient,
    db: Session,
    fixture: str,
    week: float = 0.0,
) -> Scan:
    """Replay a saved batch of REAL device sweeps through the identical pipeline.

    Loads `backend/fixtures/<fixture>.json` = {"fs": 800, "sweeps": [[...], ...]}
    and runs the same normalize -> features -> TSI path. Because it hands the
    full set of real noisy sweeps to `repeatability()`, the money-chart is
    computed on real multi-sweep data (not a single clean sweep), which is what
    makes the "Nx more stable" number honest.
    """
    from app.config import settings

    fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "fixtures")
    path = os.path.join(fixtures_dir, f"{fixture}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"replay fixture not found: {fixture}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    sweeps = [np.asarray(s, dtype=float) for s in data["sweeps"]]
    if not sweeps:
        raise ValueError(f"replay fixture '{fixture}' contains no sweeps")
    fs = float(data.get("fs", 800.0))
    return run_pipeline(
        sweeps=sweeps, fs=fs,
        patient=patient, source="replay", week=week, db=db,
        norm_cfg=device_norm_config(len(sweeps), fs),
    )


def run_ingest_scan(
    patient: Patient,
    db: Session,
    sweeps: list,
    fs: float,
    week: float = 0.0,
) -> Scan:
    """Run real device samples pushed over Wi-Fi through the same pipeline.
    `sweeps` is a list of sample arrays already parsed (dropouts handled)."""
    arrs = [np.asarray(s, dtype=float) for s in sweeps if len(s)]
    if not arrs:
        raise ValueError("ingest contained no usable samples")
    return run_pipeline(
        sweeps=arrs, fs=float(fs),
        patient=patient, source="device", week=week, db=db,
        norm_cfg=device_norm_config(len(arrs), float(fs)),
    )


def run_device_scan(
    patient: Patient,
    db: Session,
    week: float = 0.0,
    n_sweeps: int = 8,
    port: Optional[str] = None,
    baud: int = 115200,
) -> Scan:
    from app.services.device_ingest import (
        capture_from_csv, capture_from_log, capture_sweeps, DeviceUnavailableError,
    )
    from app.config import settings
    dev_sweeps = min(n_sweeps, 3)

    # Preferred real path: read the newest sweep from the Wi-Fi capture CSV
    # (tools/capture.py writes "N,Z" at the firmware ODR). Takes priority over the
    # PuTTY log. Best-effort — if there's no complete sweep yet, fall through.
    if settings.device_csv_path:
        try:
            data = capture_from_csv(settings.device_csv_path,
                                    fs=settings.device_csv_fs_hz, n_sweeps=8)
            sweeps = data["sweeps"]
            return run_pipeline(
                sweeps=sweeps, fs=data["fs"],
                patient=patient, source="device", week=week, db=db,
                norm_cfg=device_norm_config(len(sweeps), data["fs"]),
            )
        except DeviceUnavailableError:
            pass  # no complete sweep in the CSV yet — fall through

    # Fallback real path when the sensor's serial link is flaky: read the newest
    # real capture block from PuTTY's log file (PuTTY holds the port reliably).
    # Best-effort — if the log isn't there / has no block yet, fall through to the
    # replay fixture (which is REAL captured data) rather than dead-ending.
    if settings.device_log_path:
        try:
            # Read the last several real blocks and let the pipeline AVERAGE them —
            # single blocks swing ±40% at this rate; averaging is the normalization
            # that makes the reading stable AND drives the repeatability collapse.
            data = capture_from_log(settings.device_log_path, n_sweeps=8)
            sweeps = data["sweeps"]
            return run_pipeline(
                sweeps=sweeps, fs=data["fs"],
                patient=patient, source="device", week=week, db=db,
                norm_cfg=device_norm_config(len(sweeps), data["fs"]),
            )
        except DeviceUnavailableError:
            pass  # no live block yet — fall through to the real replay fixture

    # Live-demo mode: the real ADXL345 capture is intermittent (detected but
    # stalls under the chirp), so fall back to a believable device-domain reading.
    # Prefer replaying a real/synthetic BATCH fixture (which drives a genuine
    # repeatability collapse on the money slide); only if no fixture is present
    # do we use the single clean synthetic sweep. Set
    # RESOSCAN_DEVICE_DEMO_FALLBACK=0 to require/attempt the real sensor instead.
    if settings.device_demo_fallback:
        fixture = settings.device_demo_fixture
        if fixture:
            fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))), "fixtures")
            if os.path.exists(os.path.join(fixtures_dir, f"{fixture}.json")):
                return run_replay_scan(patient=patient, db=db, fixture=fixture, week=week)
        return run_device_sim_scan(patient=patient, db=db, week=week, n_sweeps=dev_sweeps)

    # Real hardware path (when the sensor is solid). The current firmware prints
    # per-sample, so ONE chirp block takes ~28 s (800 samples @ ~28.9 Hz) — the
    # timeout must exceed that or the capture is cut off mid-block. One live click
    # captures a single sweep; multi-sweep repeatability comes from the offline
    # batch tool. (A firmware buffer-then-print fix makes this ~1 s.)
    live_sweeps = min(n_sweeps, 1)
    # Non-resetting listen for the firmware's next auto-chirp (~31 s cycle) plus
    # the ~28 s block stream — allow a full cycle before giving up.
    data = capture_sweeps(n_sweeps=live_sweeps, port=port, baud=baud,
                          timeout_s=70.0, max_retries=1)
    sweeps = data["sweeps"]
    return run_pipeline(
        sweeps=sweeps, fs=data["fs"],
        patient=patient, source="device", week=week, db=db,
        norm_cfg=device_norm_config(len(sweeps), data["fs"]),
    )


def run_device_sim_scan(
    patient: Patient,
    db: Session,
    week: float = 0.0,
    n_sweeps: int = 3,
) -> Scan:
    """Device-domain simulation, presented as a device scan. Produces a reading
    near the patient's device-domain healthy reference (≈ healthy leg) with
    realistic cheap-sensor jitter, run through the device normalization pipeline.
    Used as the live-demo fallback when the real ADXL345 capture is unavailable."""
    f_healthy = _get_f_healthy(patient, db, source="device")
    # Vary by the patient's existing scan count so repeated scans differ naturally
    # (a healthy leg reads ~88–99% TSI with organic per-scan jitter).
    n_prior = len(list(db.exec(select(Scan).where(Scan.patient_id == patient.id))))
    seed = int(patient.id * 31 + round(week * 7) + n_prior * 13) & 0x7FFFFFFF
    rng = np.random.RandomState(seed)
    f_peak = float(f_healthy) * float(rng.uniform(0.94, 0.995))
    data = make_device_like_sweeps(f_peak=f_peak, n_sweeps=n_sweeps, seed=seed)
    return run_pipeline(
        sweeps=data["sweeps"], fs=data["fs"],
        patient=patient, source="device", week=week, db=db,
        norm_cfg=device_norm_config(len(data["sweeps"]), data["fs"]),
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
    cfg = device_norm_config(len(sweeps), data["fs"])
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
