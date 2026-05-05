"""
ResoScan Signal Generator — Chirp excitation + resonant tissue response.

Synthesizes physically accurate vibration signals for bone healing assessment.
Uses chirp (swept-sine) excitation convolved with a damped resonator impulse
response. This produces a continuous output with clear spectral peaks at the
bone's natural frequency — matching real vibration-based bone assessment.
"""

import numpy as np
from scipy.signal import lfilter


# Sampling parameters
FS = 4096          # Sampling frequency (Hz) — power of 2 for efficient FFT
DURATION = 0.5     # Signal duration (seconds)
N_SAMPLES = int(FS * DURATION)

# Chirp excitation parameters
F_START = 20.0     # Start frequency (Hz)
F_END = 1200.0     # End frequency (Hz) — sweep past expected resonances

# Healthy bone baseline
F_HEALTHY_DEFAULT = 850.0
ZETA_HEALTHY_DEFAULT = 0.025


def callus_to_frequency(callus_pct: float, f_healthy: float = F_HEALTHY_DEFAULT) -> float:
    """Convert callus stiffness percentage to resonant frequency.

    Uses square-root mapping for non-linear biomechanical realism:
    f_n = 300 + 500 * sqrt(callus_pct / 100)

    At 0% stiffness -> 300 Hz (fresh fracture)
    At 100% stiffness -> 800 Hz (remodeled bone)
    """
    callus_pct = np.clip(callus_pct, 0.0, 100.0)
    return 300.0 + 500.0 * np.sqrt(callus_pct / 100.0)


def callus_to_damping(callus_pct: float) -> float:
    """Convert callus stiffness percentage to damping ratio.

    zeta = 0.20 - 0.175 * (callus_pct / 100)^1.3

    At 0%   -> zeta = 0.20 (high damping, fresh fracture)
    At 100% -> zeta = 0.025 (low damping, healed bone)
    """
    callus_pct = np.clip(callus_pct, 0.0, 100.0)
    return 0.20 - 0.175 * (callus_pct / 100.0) ** 1.3


def generate_chirp(duration: float = DURATION, fs: int = FS,
                   f_start: float = F_START, f_end: float = F_END,
                   amplitude: float = 1.0) -> tuple:
    """Generate a linear chirp (swept-sine) excitation signal.

    x(t) = A * sin(2*pi * (f_start*t + (f_end - f_start) * t^2 / (2*T)))

    Returns:
        (time_array, signal_array)
    """
    n = int(fs * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    phase = 2.0 * np.pi * (f_start * t + (f_end - f_start) * t**2 / (2.0 * duration))
    signal = amplitude * np.sin(phase)
    return t, signal


def _resonator_coefficients(f_n: float, zeta: float, fs: int) -> tuple:
    """Compute IIR filter coefficients for a 2nd-order resonator.

    Models the bone as a single-degree-of-freedom damped harmonic oscillator.
    Transfer function: H(s) = wn^2 / (s^2 + 2*zeta*wn*s + wn^2)
    Discretized via bilinear transform.

    Returns:
        (b, a) — numerator and denominator IIR filter coefficients
    """
    wn = 2.0 * np.pi * f_n
    zeta = np.clip(zeta, 0.005, 0.95)

    # Bilinear transform: s = 2*fs*(z-1)/(z+1)
    c = 2.0 * fs
    c2 = c * c
    wn2 = wn * wn
    two_zeta_wn_c = 2.0 * zeta * wn * c

    # Denominator: s^2 + 2*zeta*wn*s + wn^2
    a0 = c2 + two_zeta_wn_c + wn2
    a1 = 2.0 * (wn2 - c2)
    a2 = c2 - two_zeta_wn_c + wn2

    # Numerator: wn^2
    b0 = wn2
    b1 = 2.0 * wn2
    b2 = wn2

    # Normalize
    b = np.array([b0 / a0, b1 / a0, b2 / a0])
    a = np.array([1.0, a1 / a0, a2 / a0])

    return b, a


def generate_resonant_response(excitation: np.ndarray, f_n: float, zeta: float,
                                fs: int = FS, amplitude: float = 1.0) -> np.ndarray:
    """Pass excitation through a resonator filter to produce tissue response.

    This is physically accurate: the chirp sweeps through frequencies, and
    when it hits the resonant frequency, the output amplitude peaks — exactly
    like real vibration-based bone assessment.

    Returns:
        Filtered response signal
    """
    b, a = _resonator_coefficients(f_n, zeta, fs)
    response = lfilter(b, a, excitation)

    # Normalize to desired amplitude
    peak = np.max(np.abs(response))
    if peak > 1e-10:
        response = response / peak * amplitude

    return response


def add_gaussian_noise(signal: np.ndarray, noise_level: float = 0.005) -> np.ndarray:
    """Add Gaussian noise to a signal.

    noise_std = noise_level * signal_rms
    """
    rms = np.sqrt(np.mean(signal**2))
    if rms < 1e-10:
        rms = 1.0
    noise_std = noise_level * rms
    noise = np.random.normal(0, noise_std, len(signal))
    return signal + noise


def generate_scan_signal(callus_pct: float, f_healthy: float = F_HEALTHY_DEFAULT,
                         implant_loose: bool = False,
                         pressure_n: float = 3.5,
                         noise_level: float = 0.005,
                         duration: float = DURATION,
                         fs: int = FS) -> dict:
    """Generate complete scan signal with all parameters derived from callus stiffness.

    This is the main entry point for signal generation. It:
    1. Computes f_n and zeta from callus stiffness
    2. Generates chirp excitation
    3. Filters through resonator (damped harmonic oscillator model)
    4. Optionally adds loose implant secondary resonance
    5. Adds Gaussian noise
    6. Scales amplitude by pressure quality

    Returns:
        dict with keys: t, excitation, response, f_n, zeta, q_factor,
                        implant_loose, pressure_n, callus_pct
    """
    f_n = callus_to_frequency(callus_pct, f_healthy)
    zeta = callus_to_damping(callus_pct)
    q_factor = 1.0 / (2.0 * zeta) if zeta > 0.001 else 500.0

    # Pressure amplitude scaling (optimal at 3.5N center of 2-5N range)
    pressure_quality = 1.0 - 0.3 * abs(pressure_n - 3.5) / 3.5
    pressure_quality = np.clip(pressure_quality, 0.3, 1.0)

    t, excitation = generate_chirp(duration, fs)

    # Primary resonant response
    response = generate_resonant_response(excitation, f_n, zeta, fs,
                                           amplitude=pressure_quality)

    # Loose implant: add secondary resonance (rattle)
    secondary_f_n = None
    secondary_zeta = None
    if implant_loose:
        secondary_f_n = f_n * 0.5  # Well-separated secondary rattle peak
        secondary_zeta = np.clip(zeta * 0.8, 0.02, 0.08)  # Sharper secondary
        secondary_amplitude = pressure_quality * np.random.uniform(0.55, 0.70)

        secondary = generate_resonant_response(excitation, secondary_f_n,
                                                secondary_zeta, fs,
                                                amplitude=secondary_amplitude)
        response = response + secondary

    # Add noise
    response = add_gaussian_noise(response, noise_level)

    return {
        "t": t,
        "excitation": excitation,
        "response": response,
        "f_n": f_n,
        "zeta": zeta,
        "q_factor": q_factor,
        "implant_loose": implant_loose,
        "secondary_f_n": secondary_f_n,
        "secondary_zeta": secondary_zeta,
        "pressure_n": pressure_n,
        "callus_pct": callus_pct,
        "fs": fs,
        "duration": duration,
    }


def generate_healthy_reference(f_healthy: float = F_HEALTHY_DEFAULT,
                               zeta_healthy: float = ZETA_HEALTHY_DEFAULT,
                               duration: float = DURATION,
                               fs: int = FS) -> dict:
    """Generate a healthy bone reference signal for PSD overlay comparison."""
    t, excitation = generate_chirp(duration, fs)
    response = generate_resonant_response(excitation, f_healthy, zeta_healthy, fs,
                                           amplitude=1.0)
    response = add_gaussian_noise(response, noise_level=0.003)

    return {
        "t": t,
        "excitation": excitation,
        "response": response,
        "f_n": f_healthy,
        "zeta": zeta_healthy,
        "q_factor": 1.0 / (2.0 * zeta_healthy),
        "fs": fs,
        "duration": duration,
    }
