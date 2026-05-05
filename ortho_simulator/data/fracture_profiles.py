"""
ResoScan Fracture Profiles — Per-fracture-type spectral signature effects.

Defines how different fracture morphologies alter the spectral response
relative to the healthy baseline. Each type has characteristic frequency
reduction, damping increase, and spectral shape modifications.
"""

import numpy as np

FRACTURE_PROFILES = {
    "Transverse": {
        "freq_drop_range": (0.30, 0.45),
        "damping_increase_range": (0.05, 0.10),
        "spectral_shape": "Clean single shifted peak",
        "description": "Perpendicular to bone axis. Clean spectral shift, single mode.",
        "healing_rate_modifier": 1.0,
    },
    "Oblique": {
        "freq_drop_range": (0.25, 0.40),
        "damping_increase_range": (0.08, 0.15),
        "spectral_shape": "Slightly broader peak",
        "description": "Angled fracture line. Broader peak due to mixed-mode vibration.",
        "healing_rate_modifier": 0.95,
    },
    "Spiral": {
        "freq_drop_range": (0.20, 0.35),
        "damping_increase_range": (0.10, 0.20),
        "spectral_shape": "Dual mode (bending + torsion)",
        "description": "Rotational injury pattern. Dual-mode response from bending and torsion.",
        "healing_rate_modifier": 0.85,
    },
    "Comminuted": {
        "freq_drop_range": (0.50, 0.80),
        "damping_increase_range": (0.25, 0.50),
        "spectral_shape": "Very broad, flat spectral hump",
        "description": "Multi-fragment fracture. Severe spectral broadening, very low Q-factor.",
        "healing_rate_modifier": 0.65,
    },
}


def get_fracture_types() -> list:
    """Return list of supported fracture types."""
    return list(FRACTURE_PROFILES.keys())


def get_fracture_profile(fracture_type: str) -> dict:
    """Get profile for a specific fracture type. Defaults to Transverse."""
    return FRACTURE_PROFILES.get(fracture_type, FRACTURE_PROFILES["Transverse"])


def apply_fracture_effects(f_healthy: float, zeta_healthy: float,
                           fracture_type: str, severity: float = 0.5) -> dict:
    """Apply fracture-specific spectral modifications at initial injury.

    severity: 0.0 (mild) to 1.0 (severe) within the fracture type's range

    Returns:
        dict with modified f_n, zeta, and additional parameters
    """
    profile = get_fracture_profile(fracture_type)

    # Interpolate within the fracture type's range based on severity
    freq_drop_min, freq_drop_max = profile["freq_drop_range"]
    freq_drop = freq_drop_min + severity * (freq_drop_max - freq_drop_min)

    damp_inc_min, damp_inc_max = profile["damping_increase_range"]
    damp_increase = damp_inc_min + severity * (damp_inc_max - damp_inc_min)

    f_injured = f_healthy * (1.0 - freq_drop)
    zeta_injured = zeta_healthy + damp_increase

    return {
        "f_injured": f_injured,
        "zeta_injured": zeta_injured,
        "freq_drop_pct": freq_drop * 100,
        "damping_increase": damp_increase,
        "spectral_shape": profile["spectral_shape"],
        "healing_rate_modifier": profile["healing_rate_modifier"],
    }
