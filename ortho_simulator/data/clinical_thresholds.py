"""
ResoScan Clinical Thresholds — TSI zones, RUST criteria, weight-bearing thresholds.

Central reference for all threshold values used in clinical decision-making.
"""

# TSI (Tibial Stiffness Index) zones
TSI_THRESHOLDS = {
    "safe_wb": 80.0,          # Above this → safe for full weight-bearing
    "partial_wb_upper": 80.0, # Upper bound for partial WB zone
    "partial_wb_lower": 60.0, # Lower bound for partial WB zone
    "non_union_concern": 40.0, # Below this after 16 weeks → non-union
    "instability": 60.0,      # Below this → instability detected
}

# Damping ratio zones
DAMPING_THRESHOLDS = {
    "solid_union": 0.03,     # Below this → solid union (green)
    "partial_healing": 0.06, # Below this → partial healing (yellow)
    # Above 0.06 → instability (red)
}

# RUST score interpretation
RUST_INTERPRETATION = {
    4: "No radiographic healing",
    5: "Minimal callus, no bridging",
    6: "Callus present, no bridging",
    7: "Callus present, partial bridging",
    8: "Bridging callus on 1-2 cortices",
    9: "Bridging callus on 2-3 cortices",
    10: "Bridging callus on 3-4 cortices",
    11: "Near-complete bridging",
    12: "Complete radiographic union",
}

# Pressure gate thresholds
PRESSURE_THRESHOLDS = {
    "min_n": 2.0,    # Minimum contact pressure (N)
    "max_n": 5.0,    # Maximum contact pressure (N)
    "optimal_n": 3.5, # Optimal center pressure (N)
}

# Q-factor interpretation
Q_FACTOR_ZONES = {
    "excellent": 15.0,   # Q > 15 → strong mechanical integrity
    "good": 8.0,         # Q > 8 → progressive stiffening
    "moderate": 4.0,     # Q > 4 → moderate callus
    # Q < 4 → significant fracture site motion
}

# Healing timeline thresholds
HEALING_THRESHOLDS = {
    "non_union_week": 16,       # Week after which non-union is suspected
    "non_union_tsi_threshold": 40.0,  # TSI below this at 16+ weeks
    "expected_healing_weeks": 12,     # Typical healing duration
}

# Weight-bearing protocol thresholds
WEIGHT_BEARING = {
    "full": {"tsi_min": 80.0, "zeta_max": 0.03, "label": "Full Weight-Bearing"},
    "partial": {"tsi_min": 60.0, "zeta_max": 0.06, "label": "Partial Weight-Bearing"},
    "touchdown": {"tsi_min": 40.0, "zeta_max": 0.10, "label": "Touch-Down Weight-Bearing"},
    "none": {"tsi_min": 0.0, "zeta_max": 1.0, "label": "Non-Weight-Bearing"},
}
