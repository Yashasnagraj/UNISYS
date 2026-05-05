"""
ResoScan Bone Profiles — Per-bone resonance parameters and measurement configurations.

Contains healthy baseline parameters for each supported bone type,
including natural frequency, damping ratio, and measurement probe placement.
"""

BONE_PROFILES = {
    "Tibia": {
        "f_healthy": 850.0,
        "zeta_healthy": 0.025,
        "measurement_from": "Medial Malleolus",
        "measurement_to": "Tibial Tuberosity",
        "typical_length_cm": 36.0,
        "description": "Most commonly assessed long bone for fracture healing monitoring",
    },
    "Femur": {
        "f_healthy": 680.0,
        "zeta_healthy": 0.030,
        "measurement_from": "Lateral Condyle",
        "measurement_to": "Greater Trochanter",
        "typical_length_cm": 45.0,
        "description": "Largest long bone; lower resonant frequency due to greater mass",
    },
    "Radius": {
        "f_healthy": 1000.0,
        "zeta_healthy": 0.020,
        "measurement_from": "Radial Styloid",
        "measurement_to": "Radial Head",
        "typical_length_cm": 24.0,
        "description": "Higher frequency due to smaller cross-section and lower mass",
    },
    "Humerus": {
        "f_healthy": 780.0,
        "zeta_healthy": 0.028,
        "measurement_from": "Lateral Epicondyle",
        "measurement_to": "Deltoid Tuberosity",
        "typical_length_cm": 33.0,
        "description": "Upper extremity long bone with moderate resonant frequency",
    },
}


def get_bone_names() -> list:
    """Return list of supported bone names."""
    return list(BONE_PROFILES.keys())


def get_bone_profile(bone_name: str) -> dict:
    """Get profile for a specific bone. Defaults to Tibia if not found."""
    return BONE_PROFILES.get(bone_name, BONE_PROFILES["Tibia"])
