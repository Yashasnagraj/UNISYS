"""
ResoScan Feature Extractor — 25 engineered features from a raw vibration signal.

Operates on the same signal pipeline used at runtime so the training
distribution matches the inference distribution exactly.

Feature groups (matches UNISYS document specification):
  Spectral (12): f_peak, A_peak, spectral_centroid, spectral_bandwidth,
                 spectral_rolloff_85, spectral_flatness, q_factor,
                 band_energy_ratio_low, band_energy_ratio_mid,
                 band_energy_ratio_high, peak_splitting_flag, secondary_peak_ratio
  Time-domain (7): rms_amplitude, peak_to_peak, crest_factor,
                   zero_crossing_rate, decay_time_ms, signal_kurtosis,
                   signal_skew
  Damping (4): damping_ratio, log_decrement, half_power_bandwidth, mdf
  Clinical (2): tsi, callus_proxy

Total: 25 features.
"""

import numpy as np
from scipy.signal import find_peaks
from scipy.stats import kurtosis, skew

from engine.fft_engine import (
    compute_psd, detect_peaks, compute_half_power_bandwidth,
    compute_modal_damping_factor,
)


FEATURE_NAMES = [
    "f_peak", "A_peak", "spectral_centroid", "spectral_bandwidth",
    "spectral_rolloff_85", "spectral_flatness", "q_factor",
    "band_energy_low", "band_energy_mid", "band_energy_high",
    "peak_splitting_flag", "secondary_peak_ratio",
    "rms_amplitude", "peak_to_peak", "crest_factor",
    "zero_crossing_rate", "decay_time_ms", "signal_kurtosis", "signal_skew",
    "damping_ratio", "log_decrement", "half_power_bandwidth", "mdf",
    "tsi", "callus_proxy",
]


def _spectral_centroid(freqs: np.ndarray, psd_linear: np.ndarray) -> float:
    total = np.sum(psd_linear)
    if total < 1e-15:
        return 0.0
    return float(np.sum(freqs * psd_linear) / total)


def _spectral_rolloff(freqs: np.ndarray, psd_linear: np.ndarray,
                     ratio: float = 0.85) -> float:
    cumulative = np.cumsum(psd_linear)
    total = cumulative[-1] if len(cumulative) else 0.0
    if total < 1e-15:
        return float(freqs[-1]) if len(freqs) else 0.0
    threshold = ratio * total
    idx = int(np.searchsorted(cumulative, threshold))
    idx = min(idx, len(freqs) - 1)
    return float(freqs[idx])


def _spectral_flatness(psd_linear: np.ndarray) -> float:
    """Wiener entropy — geometric mean / arithmetic mean of PSD.

    0 = pure tone (narrow spectrum). 1 = white noise (flat spectrum).
    Healthy bone has lower flatness; fractured / non-union has higher.
    """
    psd = psd_linear + 1e-20
    geo_mean = np.exp(np.mean(np.log(psd)))
    arith_mean = np.mean(psd)
    if arith_mean < 1e-20:
        return 0.0
    return float(geo_mean / arith_mean)


def _band_energy_ratios(freqs: np.ndarray, psd_linear: np.ndarray) -> tuple:
    """Energy in (50-300 Hz, 300-700 Hz, 700-1200 Hz) bands, normalized."""
    total = np.sum(psd_linear) + 1e-15
    low_mask = (freqs >= 50) & (freqs < 300)
    mid_mask = (freqs >= 300) & (freqs < 700)
    high_mask = (freqs >= 700) & (freqs <= 1200)
    return (
        float(np.sum(psd_linear[low_mask]) / total),
        float(np.sum(psd_linear[mid_mask]) / total),
        float(np.sum(psd_linear[high_mask]) / total),
    )


def _peak_splitting(peaks: list) -> tuple:
    """Detect peak splitting (loose implant signature).

    Returns (flag, secondary_to_primary_ratio).
    """
    if len(peaks) < 2:
        return 0, 0.0
    primary = peaks[0]
    secondary = peaks[1]
    primary_lin = 10 ** (primary["amplitude_db"] / 10.0)
    secondary_lin = 10 ** (secondary["amplitude_db"] / 10.0)
    ratio = secondary_lin / (primary_lin + 1e-15)
    flag = 1 if ratio > 0.15 else 0
    return flag, float(ratio)


def _zero_crossing_rate(signal: np.ndarray) -> float:
    sign_changes = np.sum(np.diff(np.sign(signal)) != 0)
    return float(sign_changes / len(signal))


def _decay_time_ms(signal: np.ndarray, fs: int) -> float:
    """Time for signal envelope to decay to 1/e of peak (ms).

    Higher decay time → less damping → stiffer bone.
    """
    envelope = np.abs(signal)
    peak_idx = int(np.argmax(envelope))
    peak_val = envelope[peak_idx]
    if peak_val < 1e-10:
        return 0.0
    threshold = peak_val / np.e
    for i in range(peak_idx, len(envelope)):
        if envelope[i] < threshold:
            return float((i - peak_idx) / fs * 1000.0)
    return float((len(envelope) - peak_idx) / fs * 1000.0)


def _log_decrement_from_peaks(signal: np.ndarray, fs: int) -> float:
    min_dist = max(int(fs / 2000), 3)
    peak_idx, _ = find_peaks(signal, distance=min_dist)
    if len(peak_idx) < 2:
        return 0.0
    amps = np.abs(signal[peak_idx])
    amps = amps[amps > 0.05 * amps.max()]
    if len(amps) < 2:
        return 0.0
    ratios = []
    for i in range(min(len(amps) - 1, 8)):
        if amps[i + 1] > 1e-10 and amps[i] > amps[i + 1]:
            ld = np.log(amps[i] / amps[i + 1])
            if 0 < ld < 5:
                ratios.append(ld)
    return float(np.mean(ratios)) if ratios else 0.0


def extract_features(signal: np.ndarray, fs: int, f_healthy: float,
                     callus_pct: float) -> dict:
    """Run full feature extraction pipeline on a raw vibration signal.

    Returns a dict with all 25 features (keys match FEATURE_NAMES).
    """
    # --- Spectral analysis ---
    psd_result = compute_psd(signal, fs=fs, n_fft=2048)
    freqs = psd_result["freqs"]
    psd_lin = psd_result["psd_linear"]
    psd_db = psd_result["psd_db"]

    peaks = detect_peaks(psd_db, freqs)

    if peaks:
        primary = peaks[0]
        f_peak = primary["freq"]
        A_peak = primary["amplitude_db"]
        bw_result = compute_half_power_bandwidth(psd_db, freqs, primary["index"])
        q_factor = bw_result["q_factor"]
        zeta_meas = bw_result["zeta_measured"]
        bandwidth = bw_result["bandwidth_hz"]
    else:
        f_peak = 0.0
        A_peak = 0.0
        q_factor = 1.0
        zeta_meas = 0.5
        bandwidth = 100.0

    centroid = _spectral_centroid(freqs, psd_lin)
    rolloff = _spectral_rolloff(freqs, psd_lin, 0.85)
    flatness = _spectral_flatness(psd_lin)
    bel_low, bel_mid, bel_high = _band_energy_ratios(freqs, psd_lin)
    split_flag, sec_ratio = _peak_splitting(peaks)

    # --- Time-domain ---
    rms = float(np.sqrt(np.mean(signal ** 2)))
    p2p = float(np.max(signal) - np.min(signal))
    crest = float(np.max(np.abs(signal)) / rms) if rms > 1e-15 else 0.0
    zcr = _zero_crossing_rate(signal)
    decay_ms = _decay_time_ms(signal, fs)
    kurt = float(kurtosis(signal))
    skw = float(skew(signal))

    # --- Damping ---
    log_dec = _log_decrement_from_peaks(signal, fs)
    mdf = compute_modal_damping_factor(signal, fs)

    # --- Clinical ---
    tsi = (f_peak / f_healthy) * 100.0 if f_healthy > 0 else 0.0
    callus_proxy = (f_peak - 300.0) / 5.0  # inverse of callus_to_frequency

    return {
        "f_peak": f_peak,
        "A_peak": A_peak,
        "spectral_centroid": centroid,
        "spectral_bandwidth": bandwidth,
        "spectral_rolloff_85": rolloff,
        "spectral_flatness": flatness,
        "q_factor": q_factor,
        "band_energy_low": bel_low,
        "band_energy_mid": bel_mid,
        "band_energy_high": bel_high,
        "peak_splitting_flag": split_flag,
        "secondary_peak_ratio": sec_ratio,
        "rms_amplitude": rms,
        "peak_to_peak": p2p,
        "crest_factor": crest,
        "zero_crossing_rate": zcr,
        "decay_time_ms": decay_ms,
        "signal_kurtosis": kurt,
        "signal_skew": skw,
        "damping_ratio": zeta_meas,
        "log_decrement": log_dec,
        "half_power_bandwidth": bandwidth,
        "mdf": mdf,
        "tsi": tsi,
        "callus_proxy": callus_proxy,
    }
