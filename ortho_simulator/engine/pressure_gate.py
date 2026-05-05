"""
ResoScan Pressure Gate — Contact pressure validation for scan quality assurance.

Ensures transducer contact pressure is within the optimal 2-5N range
before allowing scan acquisition. Prevents unreliable measurements
from insufficient or excessive contact force.
"""


def evaluate_pressure(pressure_n: float) -> dict:
    """Evaluate transducer contact pressure for scan readiness.

    Optimal range: 2.0 - 5.0 N
    Below 2.0 N → Too light, unreliable coupling
    Above 5.0 N → Excessive, may alter bone response

    Returns:
        dict with status, color, hex, scan_enabled, message
    """
    if pressure_n < 2.0:
        return {
            "status": "TOO_LIGHT",
            "color": "yellow",
            "hex": "#eab308",
            "scan_enabled": False,
            "message": f"Contact pressure {pressure_n:.1f}N — insufficient coupling. "
                       f"Increase to ≥2.0N for reliable measurement.",
            "quality_pct": max(0, pressure_n / 2.0 * 60),
        }
    elif pressure_n > 5.0:
        return {
            "status": "EXCESSIVE",
            "color": "red",
            "hex": "#ef4444",
            "scan_enabled": False,
            "message": f"Contact pressure {pressure_n:.1f}N — excessive force. "
                       f"Reduce to ≤5.0N to avoid measurement artifact.",
            "quality_pct": max(0, 100 - (pressure_n - 5.0) * 20),
        }
    else:
        # Optimal: peak quality at 3.5N center
        quality = 100 - 20 * abs(pressure_n - 3.5)
        quality = max(80, min(100, quality))
        return {
            "status": "OPTIMAL",
            "color": "green",
            "hex": "#22c55e",
            "scan_enabled": True,
            "message": f"Contact pressure {pressure_n:.1f}N — optimal coupling achieved.",
            "quality_pct": quality,
        }
