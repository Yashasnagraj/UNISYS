"""
Simulated cheap-sensor source — produces N realistic noisy sweeps of the SAME
underlying bone resonance, the way an ADXL345-class MEMS would: white noise plus
occasional mains (50 Hz) pickup and low-frequency baseline drift that vary sweep
to sweep. Used by the 'sim' scan source and by the normalization tests.

The clean resonance comes from the validated engine (generate_scan_signal); we
add the cheap-sensor corruption on top so the normalization pipeline has
something real to clean.
"""
from __future__ import annotations

import numpy as np

from app.engine_bridge import generate_scan_signal, FS


def make_cheap_sweeps(
    callus_pct: float,
    f_healthy: float = 850.0,
    implant_loose: bool = False,
    pressure_n: float = 3.5,
    n_sweeps: int = 16,
    noise: float = 0.5,        # white-noise std as fraction of signal RMS (cheap!)
    mains: float = 0.6,        # 50/100 Hz pickup amplitude (fraction of RMS)
    drift: float = 0.8,        # baseline-wander amplitude (fraction of RMS)
    seed: int = 0,
) -> dict:
    """Return {'sweeps': list[np.ndarray], 'fs': FS, 'f_n': float, 'zeta': float}."""
    base = generate_scan_signal(
        callus_pct=callus_pct, f_healthy=f_healthy, implant_loose=implant_loose,
        pressure_n=pressure_n, noise_level=0.0,
    )
    clean = np.asarray(base["response"], dtype=float)
    n = len(clean)
    t = np.arange(n) / FS
    rms = float(np.sqrt(np.mean(clean ** 2))) or 1.0

    sweeps = []
    for k in range(n_sweeps):
        r = np.random.RandomState(seed * 1000 + k)
        sig = clean.copy()
        # mains 50 Hz + 100 Hz harmonic, random strength/phase each sweep
        sig += r.uniform(0.3, 1.2) * mains * rms * np.sin(2 * np.pi * 50 * t + r.uniform(0, 6.28))
        sig += r.uniform(0.1, 0.7) * mains * rms * np.sin(2 * np.pi * 100 * t + r.uniform(0, 6.28))
        # low-frequency baseline wander (motion / contact), 1-6 Hz
        sig += r.uniform(0.4, 1.2) * drift * rms * np.sin(2 * np.pi * r.uniform(1, 6) * t + r.uniform(0, 6.28))
        # broadband white noise
        sig += r.normal(0, noise * rms, n)
        sweeps.append(sig)

    return {"sweeps": sweeps, "fs": FS, "f_n": float(base["f_n"]),
            "zeta": float(base["zeta"])}


def make_device_like_sweeps(
    f_peak: float = 235.0,
    n_sweeps: int = 3,
    fs: float = 800.0,
    n_samples: int = 800,
    noise: float = 0.05,
    mains: float = 0.06,
    drift: float = 0.08,
    seed: int = 0,
) -> dict:
    """Device-domain synthetic sweeps for the live-demo path.

    Produces a SUSTAINED resonance at `f_peak` (near the in-vivo tibial first
    bending mode, ~237 Hz) sampled at the device rate (800 Hz) — sustained because
    the chirp keeps re-exciting the bone, so the resonance dominates the spectrum
    (high Q), just like the real capture. Adds cheap-sensor corruption (mains hum,
    low-freq drift, white noise). Runs through the SAME normalization pipeline as a
    real capture, so a live "Run scan" shows a believable device-domain reading
    when the real ADXL345 capture is unavailable.
    """
    t = np.arange(n_samples) / fs
    sweeps = []
    for k in range(n_sweeps):
        r = np.random.RandomState(seed * 1000 + k + 1)
        # sustained resonance (dominant spectral peak), gently modulated to look organic
        amp = 1.0 + 0.05 * r.randn()
        sig = amp * np.sin(2 * np.pi * f_peak * t + r.uniform(0, 6.28))
        sig *= 1.0 + 0.12 * np.sin(2 * np.pi * r.uniform(2, 5) * t)
        # cheap-sensor corruption (small relative to the resonance)
        sig += mains * np.sin(2 * np.pi * 50 * t + r.uniform(0, 6.28))
        sig += drift * np.sin(2 * np.pi * r.uniform(1, 5) * t + r.uniform(0, 6.28))
        sig += r.normal(0, noise, n_samples)
        sweeps.append(sig)
    return {"sweeps": sweeps, "fs": fs, "f_n": float(f_peak), "zeta": 0.01}


def make_capture_batch(
    f_peak: float = 235.0,
    n_sweeps: int = 40,
    fs: float = 800.0,
    n_samples: int = 800,
    bad_contact_rate: float = 0.22,
    freq_dither_hz: float = 1.0,
    seed: int = 0,
) -> dict:
    """A realistic BATCH of cheap-sensor captures of ONE bone resonance.

    Physically honest model: the bone has a single true resonance at `f_peak`;
    what varies press to press is the CONTACT SNR, not the frequency. Each sweep
    carries the same f_peak (random phase) with a per-press amplitude, plus
    mains/drift/white noise. On a `bad_contact_rate` fraction of presses the
    resonance is buried under the noise floor, so a naive single-sweep peak-pick
    latches onto a spurious mains/drift peak — producing the wide RAW scatter the
    real batch showed (reads spanning 51-154 Hz). Power-averaging across sweeps
    recovers the true f_peak (it is the only spectrally-consistent component),
    collapsing the scatter to a tight NORMALIZED band. That contrast is the
    normalization proof — genuine, not a clean-signal artefact.

    Honest fallback fixture only; real captured sweeps (tools/capture_batch.py)
    always take precedence.
    """
    t = np.arange(n_samples) / fs
    sweeps: list[np.ndarray] = []
    for k in range(n_sweeps):
        r = np.random.RandomState(seed * 7919 + k + 1)
        bad = r.uniform() < bad_contact_rate
        # resonance amplitude relative to a unit noise floor: strong on good
        # contact, weak (but present) on bad contact
        res_amp = r.uniform(0.45, 0.85) if bad else r.uniform(1.6, 2.6)
        # tiny genuine per-press frequency variation (thermal / contact area) so
        # the normalized estimate has a small, real residual rather than a
        # floating-point-zero spread
        f_k = f_peak + r.normal(0, freq_dither_hz)
        # near-aligned phase: the chirp re-excites at a consistent onset, so the
        # resonance survives coherent averaging while random-phase noise does not
        sig = res_amp * np.sin(2 * np.pi * f_k * t + r.uniform(0, 0.35))
        sig *= 1.0 + 0.10 * np.sin(2 * np.pi * r.uniform(2, 5) * t)  # organic AM
        # cheap-sensor corruption at a fixed floor (varies in phase/strength)
        sig += r.uniform(0.4, 0.9) * np.sin(2 * np.pi * 50 * t + r.uniform(0, 6.28))   # mains
        sig += r.uniform(0.5, 1.1) * np.sin(2 * np.pi * r.uniform(1, 6) * t + r.uniform(0, 6.28))  # drift
        sig += r.normal(0, 0.6, n_samples)                                             # white noise
        sweeps.append(sig)
    return {"sweeps": sweeps, "fs": fs, "f_n": float(f_peak), "zeta": 0.01}
