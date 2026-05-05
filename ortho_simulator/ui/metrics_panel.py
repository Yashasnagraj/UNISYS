"""
ResoScan Metrics Panel — Right panel displaying TSI, RUST, damping, Q-factor.

Renders clinical metrics as styled cards with color-coded status indicators,
including the RUST 4-cortex visual breakdown.
"""

import streamlit as st
from ui.styles import metric_card_html, cortex_grid_html, badge_html
from engine.clinical_metrics import interpret_damping, compute_rust_cortex_scores
from data.clinical_thresholds import Q_FACTOR_ZONES


def render_metrics_panel(tsi: float, rust: int, f_n: float, zeta: float,
                         q_factor: float, mdf: float, bandwidth: float):
    """Render the right-side metrics panel with all clinical values.

    Args:
        tsi: Tibial Stiffness Index (%)
        rust: RUST score (4-12)
        f_n: Resonant frequency (Hz)
        zeta: Damping ratio
        q_factor: Quality factor
        mdf: Modal Damping Factor
        bandwidth: -3dB bandwidth (Hz)
    """
    st.markdown('<div class="section-header">CLINICAL METRICS</div>',
                unsafe_allow_html=True)

    # TSI — with color based on zone
    if tsi > 80:
        tsi_color = "#22c55e"
    elif tsi > 60:
        tsi_color = "#eab308"
    else:
        tsi_color = "#ef4444"

    st.markdown(
        metric_card_html("Tibial Stiffness Index (TSI)", f"{tsi:.1f}", "%", tsi_color),
        unsafe_allow_html=True,
    )

    # TSI progress bar
    st.progress(min(tsi / 100.0, 1.0))

    # RUST Score
    rust_color = "#22c55e" if rust >= 10 else "#eab308" if rust >= 7 else "#ef4444"
    st.markdown(
        metric_card_html("RUST Score", f"{rust}", "/12", rust_color),
        unsafe_allow_html=True,
    )

    # RUST cortex breakdown
    cortex_scores = compute_rust_cortex_scores(tsi)
    st.markdown(cortex_grid_html(cortex_scores), unsafe_allow_html=True)

    st.markdown("---")

    # Resonant Frequency
    st.markdown(
        metric_card_html("Resonant Frequency", f"{f_n:.0f}", "Hz", "#06b6d4"),
        unsafe_allow_html=True,
    )

    # Damping Ratio + interpretation
    damping_info = interpret_damping(zeta)
    st.markdown(
        metric_card_html("Damping Ratio (ζ)", f"{zeta:.4f}", "", damping_info["hex"]),
        unsafe_allow_html=True,
    )
    st.markdown(
        badge_html(damping_info["label"], damping_info["color"]),
        unsafe_allow_html=True,
    )

    # Q-Factor
    if q_factor > Q_FACTOR_ZONES["excellent"]:
        q_color = "#22c55e"
        q_label = "Excellent"
    elif q_factor > Q_FACTOR_ZONES["good"]:
        q_color = "#06b6d4"
        q_label = "Good"
    elif q_factor > Q_FACTOR_ZONES["moderate"]:
        q_color = "#eab308"
        q_label = "Moderate"
    else:
        q_color = "#ef4444"
        q_label = "Low"

    st.markdown(
        metric_card_html("Q-Factor", f"{q_factor:.1f}", "", q_color),
        unsafe_allow_html=True,
    )
    st.caption(f"{q_label} — Higher Q = Stronger Bone")

    st.markdown("---")

    # Secondary metrics
    st.markdown(
        metric_card_html("Modal Damping (MDF)", f"{mdf:.4f}", ""),
        unsafe_allow_html=True,
    )

    st.markdown(
        metric_card_html("-3dB Bandwidth", f"{bandwidth:.1f}", "Hz"),
        unsafe_allow_html=True,
    )
