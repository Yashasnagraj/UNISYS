"""
ResoScan Sidebar — Left panel controls, sliders, toggles, and patient info.

Provides all user-facing controls for the simulator including bone selection,
fracture type, callus stiffness slider, pressure control, implant toggle,
and scan initiation button.
"""

import streamlit as st
from data.bone_profiles import get_bone_names, get_bone_profile
from data.fracture_profiles import get_fracture_types
from engine.pressure_gate import evaluate_pressure
from ui.styles import pressure_gauge_html, badge_html


def render_sidebar() -> dict:
    """Render the sidebar controls and return all parameter values.

    Returns:
        dict with all user-selected parameters
    """
    with st.sidebar:
        # Title
        st.markdown(
            '<div class="section-header">RESOSCAN CONTROLS</div>',
            unsafe_allow_html=True,
        )

        # --- Patient Info ---
        st.markdown("##### Patient Configuration")

        bone = st.selectbox(
            "Bone",
            options=get_bone_names(),
            index=0,
            help="Select the bone being assessed",
        )

        bone_profile = get_bone_profile(bone)

        fracture_type = st.selectbox(
            "Fracture Type",
            options=get_fracture_types(),
            index=0,
            help="Select fracture morphology",
        )

        st.caption(
            f"Measurement: {bone_profile['measurement_from']} → {bone_profile['measurement_to']}"
        )

        st.divider()

        # --- Callus Stiffness ---
        st.markdown("##### Callus Stiffness")
        callus_pct = st.slider(
            "Stiffness (%)",
            min_value=0,
            max_value=100,
            value=50,
            step=1,
            help="0% = fresh fracture, 100% = fully remodeled bone",
        )

        # Show derived parameters
        from engine.signal_generator import callus_to_frequency, callus_to_damping
        f_n_preview = callus_to_frequency(callus_pct, bone_profile["f_healthy"])
        zeta_preview = callus_to_damping(callus_pct)
        st.caption(f"f₀ ≈ {f_n_preview:.0f} Hz  |  ζ ≈ {zeta_preview:.3f}")

        st.divider()

        # --- Contact Pressure ---
        st.markdown("##### Contact Pressure")
        pressure_n = st.slider(
            "Pressure (N)",
            min_value=0.0,
            max_value=7.0,
            value=3.5,
            step=0.1,
            help="Transducer contact force. Optimal: 2.0-5.0 N",
        )

        pressure_result = evaluate_pressure(pressure_n)

        # Pressure gauge
        st.markdown(
            pressure_gauge_html(pressure_n, pressure_result["color"]),
            unsafe_allow_html=True,
        )

        badge_color = pressure_result["color"]
        st.markdown(
            badge_html(
                f"{pressure_result['status']} — {pressure_n:.1f}N",
                badge_color,
            ),
            unsafe_allow_html=True,
        )

        st.divider()

        # --- Implant Toggle ---
        st.markdown("##### Hardware Status")
        implant_loose = st.checkbox(
            "Simulate Loose Implant",
            value=False,
            help="Adds secondary spectral peak (implant rattle artifact)",
        )

        st.divider()

        # --- Healing Week ---
        st.markdown("##### Timeline Position")
        week = st.slider(
            "Week",
            min_value=0,
            max_value=16,
            value=8,
            step=1,
            help="Current week post-injury for timeline context",
        )

        non_union = st.checkbox(
            "Simulate Non-Union",
            value=False,
            help="Show non-union trajectory (plateaus at ~30%)",
        )

        st.divider()

        # --- Scan Button ---
        scan_enabled = pressure_result["scan_enabled"]
        scan_pressed = st.button(
            "🔬 START SCAN" if scan_enabled else "⚠ ADJUST PRESSURE",
            disabled=not scan_enabled,
            use_container_width=True,
            type="primary" if scan_enabled else "secondary",
        )

        if not scan_enabled:
            st.warning(pressure_result["message"])

        st.divider()

        # --- Info Footer ---
        st.caption("ResoScan v1.0 — Resonant Modal Spectroscopy")
        st.caption("Simulation tool. Not for clinical use.")

    return {
        "bone": bone,
        "bone_profile": bone_profile,
        "fracture_type": fracture_type,
        "callus_pct": callus_pct,
        "pressure_n": pressure_n,
        "pressure_result": pressure_result,
        "implant_loose": implant_loose,
        "week": week,
        "non_union": non_union,
        "scan_pressed": scan_pressed,
        "scan_enabled": scan_enabled,
    }
