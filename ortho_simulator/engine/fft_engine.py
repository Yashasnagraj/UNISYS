"""
ResoScan FFT Engine — Real DSP using NumPy/SciPy.

Computes Power Spectral Density (PSD), peak detection, half-power bandwidth,
Q-factor estimation, and spectrogram generation from time-domain signals.
Uses Welch's method for robust PSD estimation and proper Hanning windowing.
"""

import numpy as np
from scipy.signal import windows, find_peaks, stft, welch
from scipy.fft import fft, fftfreq


def compute_psd(signal: np.ndarray, fs: int = 4096, n_fft: int = 1024) -> dict:
    """Compute Power Spectral Density using Welch's method.

    Uses overlapping Hanning-windowed segments for robust estimation.
    Falls back to single-segment FFT if signal is too short.

    Returns:
        dict with keys: freqs, psd_linear, psd_db
    """
    nperseg = min(n_fft, len(signal))

    freqs, psd_linear = welch(
        signal, fs=fs, window='hann', nperseg=nperseg,
        noverlap=nperseg // 2, nfft=n_fft,
        scaling='density', detrend='constant',
    )

    # Convert to dB (reference: 1e-12)
    psd_db = 10.0 * np.log10(psd_linear / 1e-12 + 1e-30)

    return {
        "freqs": freqs,
        "psd_linear": psd_linear,
        "psd_db": psd_db,
        "freq_resolution": freqs[1] - freqs[0] if len(freqs) > 1 else 1.0,
    }


def detect_peaks(psd_db: np.ndarray, freqs: np.ndarray,
                 prominence: float = 6.0, distance: int = 8,
                 max_peaks: int = 5, min_freq: float = 50.0,
                 max_freq: float = 1400.0) -> list:
    """Detect spectral peaks in the PSD.

    Uses scipy.signal.find_peaks with prominence-based detection.
    Filters out peaks below min_freq to avoid DC/low-frequency artifacts.

    Returns:
        List of dicts with keys: freq, amplitude_db, index
    """
    # Only search within clinically relevant range
    freq_mask = (freqs >= min_freq) & (freqs <= max_freq)
    search_psd = psd_db.copy()
    search_psd[~freq_mask] = -np.inf

    peak_indices, properties = find_peaks(
        search_psd, prominence=prominence, distance=distance
    )

    peaks = []
    for idx in peak_indices:
        peaks.append({
            "freq": float(freqs[idx]),
            "amplitude_db": float(psd_db[idx]),
            "index": int(idx),
        })

    # Sort by amplitude (strongest first) and limit
    peaks.sort(key=lambda p: p["amplitude_db"], reverse=True)
    return peaks[:max_peaks]


def compute_half_power_bandwidth(psd_db: np.ndarray, freqs: np.ndarray,
                                  peak_index: int) -> dict:
    """Compute -3dB (half-power) bandwidth around a spectral peak.

    Finds the frequencies where PSD drops 3 dB below the peak value.
    Q = f_peak / bandwidth_3dB
    zeta_measured = 1 / (2 * Q)

    Returns:
        dict with keys: bandwidth_hz, q_factor, zeta_measured, f_lower, f_upper
    """
    peak_db = psd_db[peak_index]
    threshold_db = peak_db - 3.0

    # Search left for -3dB point
    f_lower = freqs[0]
    for i in range(peak_index, -1, -1):
        if psd_db[i] < threshold_db:
            if i + 1 < len(freqs):
                denom = psd_db[i + 1] - psd_db[i]
                if abs(denom) > 1e-10:
                    frac = (threshold_db - psd_db[i]) / denom
                else:
                    frac = 0.5
                f_lower = freqs[i] + frac * (freqs[i + 1] - freqs[i])
            else:
                f_lower = freqs[i]
            break

    # Search right for -3dB point
    f_upper = freqs[-1]
    for i in range(peak_index, len(psd_db)):
        if psd_db[i] < threshold_db:
            if i - 1 >= 0:
                denom = psd_db[i] - psd_db[i - 1]
                if abs(denom) > 1e-10:
                    frac = (threshold_db - psd_db[i - 1]) / denom
                else:
                    frac = 0.5
                f_upper = freqs[i - 1] + frac * (freqs[i] - freqs[i - 1])
            else:
                f_upper = freqs[i]
            break

    bandwidth = max(f_upper - f_lower, 0.1)
    f_peak = freqs[peak_index]
    q_factor = f_peak / bandwidth
    zeta_measured = 1.0 / (2.0 * q_factor) if q_factor > 0 else 0.5

    return {
        "bandwidth_hz": float(bandwidth),
        "q_factor": float(q_factor),
        "zeta_measured": float(zeta_measured),
        "f_lower": float(f_lower),
        "f_upper": float(f_upper),
    }


def compute_spectrogram(signal: np.ndarray, fs: int = 4096,
                        nperseg: int = 256, noverlap: int = 224) -> dict:
    """Compute Short-Time Fourier Transform spectrogram.

    Returns:
        dict with keys: frequencies, times, magnitude_db
    """
    f, t, Zxx = stft(signal, fs=fs, nperseg=nperseg, noverlap=noverlap,
                     window='hann')

    magnitude = np.abs(Zxx)
    magnitude_db = 20.0 * np.log10(magnitude + 1e-30)

    return {
        "frequencies": f,
        "times": t,
        "magnitude_db": magnitude_db,
    }


def compute_modal_damping_factor(signal: np.ndarray, fs: int = 4096) -> float:
    """Compute Modal Damping Factor from successive time-domain peaks.

    MDF = log_decrement / (2*pi)
    log_decrement = ln(A_n / A_{n+1})

    Returns:
        MDF value (float)
    """
    min_distance = max(int(fs / 2000), 3)
    peak_indices, _ = find_peaks(signal, distance=min_distance)

    if len(peak_indices) < 2:
        return 0.0

    amplitudes = np.abs(signal[peak_indices])
    significant = amplitudes[amplitudes > 0.05 * amplitudes.max()]
    if len(significant) < 2:
        return 0.0

    log_decrements = []
    for i in range(min(len(significant) - 1, 8)):
        if significant[i + 1] > 1e-10 and significant[i] > significant[i + 1]:
            ld = np.log(significant[i] / significant[i + 1])
            if 0 < ld < 5:
                log_decrements.append(ld)

    if not log_decrements:
        return 0.0

    avg_log_decrement = np.mean(log_decrements)
    mdf = avg_log_decrement / (2.0 * np.pi)
    return float(mdf)


def full_spectral_analysis(signal: np.ndarray, fs: int = 4096,
                           n_fft: int = 2048) -> dict:
    """Run complete spectral analysis pipeline.

    Combines PSD computation, peak detection, bandwidth analysis,
    and MDF estimation.

    Returns:
        dict with all spectral analysis results
    """
    psd_result = compute_psd(signal, fs, n_fft)
    peaks = detect_peaks(psd_result["psd_db"], psd_result["freqs"])

    bandwidth_results = []
    for peak in peaks:
        bw = compute_half_power_bandwidth(
            psd_result["psd_db"], psd_result["freqs"], peak["index"]
        )
        bandwidth_results.append({**peak, **bw})

    mdf = compute_modal_damping_factor(signal, fs)
    spectrogram = compute_spectrogram(signal, fs)

    return {
        "psd": psd_result,
        "peaks": bandwidth_results,
        "mdf": mdf,
        "spectrogram": spectrogram,
        "primary_peak": bandwidth_results[0] if bandwidth_results else None,
    }
