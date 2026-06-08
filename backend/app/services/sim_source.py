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
