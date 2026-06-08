"""
ResoScan normalization pipeline — the core IP.

Turns raw, noisy, cheap-MEMS sweeps into a clean, stable, repeatable resonant
frequency (and therefore a stable TSI). Every stage is research-backed and each
returns BOTH its output signal and a serializable snapshot so the UI can show
RAW vs NORMALIZED side by side.

Pipeline (per the plan, Part A4):
  1. coherent averaging of N sweeps        -> SNR up by sqrt(N)        (sqrt-N rule)
  2. linear detrend                        -> kills DC/baseline drift  (IEEE 9816042)
  3. Butterworth band-pass (zero-phase)    -> removes gravity/electrical noise
  4. z-score normalization                 -> removes contact-force amplitude variation
  5. Welch PSD (Hann, 50% overlap)         -> low-variance spectrum    (Welch 1967)
  6. parabolic sub-bin peak interpolation  -> sub-Hz f_peak            (Smith & Serra 1987)

The headline metric (RepeatabilityReport) computes TSI on each raw sweep vs each
normalized sweep and reports the collapse in standard deviation — the slide where
a noisy cloud becomes a tight line.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
from scipy.signal import detrend as _sp_detrend, butter, sosfiltfilt

from app.engine_bridge import compute_psd, detect_peaks, compute_half_power_bandwidth
from app.services.tsi import compute_tsi_squared


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
@dataclass
class NormConfig:
    n_sweeps: int = 8
    detrend: bool = True
    bandpass: bool = True
    band_low_hz: float = 150.0      # band of interest (sim resonance 300-850 Hz)
    band_high_hz: float = 1100.0
    bp_order: int = 4
    zscore: bool = True
    welch_nfft: int = 2048
    subbin_interp: bool = True
    # peak search window (Hz) — kept wide; band-pass already constrains content
    peak_lo_hz: float = 100.0
    peak_hi_hz: float = 1300.0

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
#  Individual stages (each pure + testable)
# --------------------------------------------------------------------------- #
def average_sweeps(sweeps: list[np.ndarray]) -> tuple[np.ndarray, float]:
    """Coherent average of N aligned sweeps. Returns (mean, snr_gain_db = 10log10 N)."""
    arr = np.asarray(sweeps, dtype=float)
    mean = arr.mean(axis=0)
    n = max(1, arr.shape[0])
    return mean, 10.0 * math.log10(n)


def detrend_linear(sig: np.ndarray) -> np.ndarray:
    return _sp_detrend(np.asarray(sig, dtype=float), type="linear")


def bandpass(sig: np.ndarray, fs: float, lo: float, hi: float, order: int = 4) -> np.ndarray:
    nyq = fs / 2.0
    lo_n = max(1e-4, lo / nyq)
    hi_n = min(0.999, hi / nyq)
    if lo_n >= hi_n:
        return np.asarray(sig, dtype=float)
    sos = butter(order, [lo_n, hi_n], btype="bandpass", output="sos")
    return sosfiltfilt(sos, np.asarray(sig, dtype=float))


def zscore(sig: np.ndarray) -> np.ndarray:
    sig = np.asarray(sig, dtype=float)
    sd = sig.std()
    if sd < 1e-12:
        return sig - sig.mean()
    return (sig - sig.mean()) / sd


def _parabolic_subbin(log_mag: np.ndarray, k: int) -> float:
    """Fractional-bin offset of the peak via parabolic interpolation on
    log-magnitude (Smith & Serra 1987). Returns offset in [-0.5, 0.5]."""
    if k <= 0 or k >= len(log_mag) - 1:
        return 0.0
    ym1, y0, yp1 = log_mag[k - 1], log_mag[k], log_mag[k + 1]
    denom = (ym1 - 2.0 * y0 + yp1)
    if abs(denom) < 1e-12:
        return 0.0
    return float(np.clip(0.5 * (ym1 - yp1) / denom, -0.5, 0.5))


def naive_peak_frequency(sig: np.ndarray, fs: float, cfg: NormConfig) -> float:
    """A deliberately naive reader: single Welch PSD, NO cleaning, WIDE search
    band, low prominence — i.e. what you get if you trust one raw cheap-sensor
    sweep. Vulnerable to mains/drift/spurious peaks. Used as the 'raw' baseline."""
    psd = compute_psd(sig, fs=int(fs), n_fft=cfg.welch_nfft)
    peaks = detect_peaks(psd["psd_db"], psd["freqs"], prominence=3.0, distance=4,
                         min_freq=20.0, max_freq=fs / 2.0 - 10.0)
    return float(peaks[0]["freq"]) if peaks else 0.0


def peak_frequency(sig: np.ndarray, fs: float, cfg: NormConfig) -> dict:
    """Welch PSD -> strongest peak in [peak_lo, peak_hi] -> sub-bin refined f_peak.
    Returns f_peak_hz, zeta, q_factor, bandwidth_hz, snr_db, peak_index."""
    psd = compute_psd(sig, fs=int(fs), n_fft=cfg.welch_nfft)
    freqs, psd_db, psd_lin = psd["freqs"], psd["psd_db"], psd["psd_linear"]
    peaks = detect_peaks(psd_db, freqs, min_freq=cfg.peak_lo_hz, max_freq=cfg.peak_hi_hz)
    if not peaks:
        return {"f_peak_hz": 0.0, "zeta": None, "q_factor": None,
                "bandwidth_hz": None, "snr_db": 0.0, "peak_index": -1,
                "freqs": freqs, "psd_db": psd_db, "psd_linear": psd_lin}
    top = peaks[0]
    k = top["index"]
    df = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    f_peak = top["freq"]
    if cfg.subbin_interp:
        log_mag = 10.0 * np.log10(psd_lin + 1e-30)
        f_peak = f_peak + _parabolic_subbin(log_mag, k) * df
    bw = compute_half_power_bandwidth(psd_db, freqs, k)
    # SNR: peak power vs median noise floor (band-limited)
    band = (freqs >= cfg.peak_lo_hz) & (freqs <= cfg.peak_hi_hz)
    floor = np.median(psd_lin[band]) if band.any() else np.median(psd_lin)
    snr_db = 10.0 * math.log10((psd_lin[k] + 1e-30) / (floor + 1e-30))
    return {"f_peak_hz": float(f_peak), "zeta": bw["zeta_measured"],
            "q_factor": bw["q_factor"], "bandwidth_hz": bw["bandwidth_hz"],
            "snr_db": float(snr_db), "peak_index": int(k),
            "freqs": freqs, "psd_db": psd_db, "psd_linear": psd_lin}


# --------------------------------------------------------------------------- #
#  Orchestrator
# --------------------------------------------------------------------------- #
@dataclass
class StageSnapshot:
    name: str
    note: str
    signal: list = field(default_factory=list)   # downsampled for UI


@dataclass
class NormalizationResult:
    stages: list                # list[StageSnapshot] RAW..ZSCORED
    normalized_signal: np.ndarray
    freqs: np.ndarray
    psd_db: np.ndarray
    f_peak_hz: float
    zeta: Optional[float]
    q_factor: Optional[float]
    bandwidth_hz: Optional[float]
    snr_db_raw: float
    snr_db_norm: float
    snr_gain_db: float
    config: NormConfig


def _clean_one(sig: np.ndarray, fs: float, cfg: NormConfig,
               snapshots: Optional[list] = None) -> np.ndarray:
    """Apply detrend -> bandpass -> zscore to a single sweep."""
    out = np.asarray(sig, dtype=float)
    if cfg.detrend:
        out = detrend_linear(out)
        if snapshots is not None:
            snapshots.append(StageSnapshot("detrended", "Removed DC / baseline drift",
                                           _downsample(out)))
    if cfg.bandpass:
        out = bandpass(out, fs, cfg.band_low_hz, cfg.band_high_hz, cfg.bp_order)
        if snapshots is not None:
            snapshots.append(StageSnapshot(
                "bandpassed",
                f"Butterworth {cfg.band_low_hz:.0f}-{cfg.band_high_hz:.0f} Hz",
                _downsample(out)))
    if cfg.zscore:
        out = zscore(out)
        if snapshots is not None:
            snapshots.append(StageSnapshot("zscored", "Amplitude-normalized (z-score)",
                                           _downsample(out)))
    return out


def _downsample(sig: np.ndarray, n: int = 256) -> list:
    sig = np.asarray(sig, dtype=float)
    if len(sig) <= n:
        return [round(float(x), 5) for x in sig]
    idx = np.linspace(0, len(sig) - 1, n).astype(int)
    return [round(float(sig[i]), 5) for i in idx]


def normalize(sweeps: list[np.ndarray], fs: float,
              cfg: Optional[NormConfig] = None) -> NormalizationResult:
    """Full pipeline: average -> detrend -> bandpass -> zscore -> PSD -> sub-bin peak."""
    cfg = cfg or NormConfig()
    sweeps = [np.asarray(s, dtype=float) for s in sweeps]
    snapshots: list = [StageSnapshot("raw", "Raw sensor sweep (mean of N)",
                                     _downsample(sweeps[0]))]

    # SNR of a single raw sweep (before anything)
    raw_peak = peak_frequency(sweeps[0], fs, cfg)
    snr_raw = raw_peak["snr_db"]

    # 1. average
    averaged, snr_gain = average_sweeps(sweeps)
    snapshots.append(StageSnapshot("averaged",
                                   f"Coherent average of {len(sweeps)} sweeps (+{snr_gain:.1f} dB SNR)",
                                   _downsample(averaged)))
    # 2-4. detrend / bandpass / zscore
    cleaned = _clean_one(averaged, fs, cfg, snapshots)

    # 5-6. PSD + sub-bin peak
    pk = peak_frequency(cleaned, fs, cfg)

    return NormalizationResult(
        stages=snapshots,
        normalized_signal=cleaned,
        freqs=pk["freqs"], psd_db=pk["psd_db"],
        f_peak_hz=pk["f_peak_hz"], zeta=pk["zeta"],
        q_factor=pk["q_factor"], bandwidth_hz=pk["bandwidth_hz"],
        snr_db_raw=snr_raw, snr_db_norm=pk["snr_db"], snr_gain_db=snr_gain,
        config=cfg,
    )


# --------------------------------------------------------------------------- #
#  Repeatability — the headline "cheap sensor still works" proof
# --------------------------------------------------------------------------- #
@dataclass
class RepeatabilityReport:
    n_sweeps: int
    f_healthy_hz: float
    tsi_raw_per_sweep: list
    tsi_norm_per_sweep: list
    tsi_std_raw: float
    tsi_std_norm: float
    tsi_cv_raw: float            # coefficient of variation %
    tsi_cv_norm: float
    improvement_factor: float    # std_raw / std_norm  (>1 == win)
    snr_gain_db: float

    def to_dict(self) -> dict:
        return asdict(self)


def repeatability(sweeps: list[np.ndarray], fs: float, f_healthy: float,
                  cfg: Optional[NormConfig] = None, n_bootstrap: int = 40,
                  seed: int = 12345) -> RepeatabilityReport:
    """The demo's money chart. Two clouds of TSI estimates:

      RAW  — one naive reading per single sweep (no averaging, no filtering,
             wide-band peak pick). Jitters with noise and can be pulled off by
             mains/drift. std_raw.
      NORM — the full pipeline: average a bootstrap resample of the N sweeps,
             detrend + band-pass + z-score, then a band-limited sub-bin peak.
             Repeated `n_bootstrap` times to measure the averaged estimate's
             own spread. std_norm.

    Averaging N sweeps reduces random jitter by ~sqrt(N) (Welch 1967 / the
    sqrt-N rule); band-pass kills the mains/drift that bias the raw reading.
    improvement_factor = std_raw / std_norm.
    """
    cfg = cfg or NormConfig()
    sweeps = [np.asarray(s, dtype=float) for s in sweeps]
    n = len(sweeps)
    rng = np.random.RandomState(seed)

    # RAW: naive per-sweep estimate
    tsi_raw = [compute_tsi_squared(naive_peak_frequency(s, fs, cfg), f_healthy)
               for s in sweeps]

    # NORM: bootstrap of (average -> clean -> band-limited peak)
    tsi_norm = []
    for _ in range(n_bootstrap):
        idx = rng.randint(0, n, size=n)
        avg = np.mean(np.stack([sweeps[i] for i in idx]), axis=0)
        cleaned = _clean_one(avg, fs, cfg)
        tsi_norm.append(compute_tsi_squared(peak_frequency(cleaned, fs, cfg)["f_peak_hz"],
                                            f_healthy))

    std_raw = float(np.std(tsi_raw))
    std_norm = float(np.std(tsi_norm))
    mean_raw = float(np.mean(tsi_raw)) or 1e-9
    mean_norm = float(np.mean(tsi_norm)) or 1e-9
    improvement = std_raw / std_norm if std_norm > 1e-9 else float("inf")

    return RepeatabilityReport(
        n_sweeps=n, f_healthy_hz=float(f_healthy),
        tsi_raw_per_sweep=[round(x, 2) for x in tsi_raw],
        tsi_norm_per_sweep=[round(x, 2) for x in tsi_norm],
        tsi_std_raw=round(std_raw, 4), tsi_std_norm=round(std_norm, 4),
        tsi_cv_raw=round(100.0 * std_raw / abs(mean_raw), 3),
        tsi_cv_norm=round(100.0 * std_norm / abs(mean_norm), 3),
        improvement_factor=round(improvement, 2),
        snr_gain_db=round(10.0 * math.log10(max(1, n)), 2),
    )
