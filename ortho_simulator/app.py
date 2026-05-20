"""
ResoScan Ortho Simulator — Main Streamlit Application

Clinical-grade orthopedic triage simulator demonstrating Resonant Modal
Spectroscopy (RMS) diagnostic workflow. Built for orthopedic surgeons
and investors with scientifically accurate signal processing.

Run: streamlit run ortho_simulator/app.py
"""

import sys
import os

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import numpy as np

# Engine imports
from engine.signal_generator import (
    generate_scan_signal, generate_healthy_reference,
    callus_to_frequency, callus_to_damping,
)
from engine.fft_engine import full_spectral_analysis, compute_psd, detect_peaks
from engine.clinical_metrics import (
    compute_tsi, compute_rust, classify_healing,
    generate_clinical_summary, compute_rust_cortex_scores,
)
from engine.pressure_gate import evaluate_pressure
from engine.classification import predict_healing_status
from engine.healing_model import generate_healing_timeline

# UI imports
from ui.styles import get_custom_css
from ui.sidebar import render_sidebar
from ui.psd_chart import create_psd_chart
from ui.waveform_chart import create_waveform_chart
from ui.spectrogram_chart import create_spectrogram_chart
from ui.metrics_panel import render_metrics_panel
from ui.classification_panel import (
    render_traffic_light, render_ml_prediction, render_clinical_summary,
)
from ui.healing_timeline import create_healing_timeline
from ui.report_generator import generate_report
from ui.analysis_text import (
    get_psd_analysis, get_waveform_analysis, get_spectrogram_analysis,
    get_timeline_analysis, get_metrics_analysis, get_classification_analysis,
    get_technology_explainer,
)


# === PAGE CONFIG ===
st.set_page_config(
    page_title="ResoScan Ortho Simulator",
    page_icon="🦴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# === INJECT CUSTOM CSS ===
st.markdown(get_custom_css(), unsafe_allow_html=True)

# === TITLE BAR ===
st.markdown(
    '<div class="title-bar">'
    '<h1>RESOSCAN ORTHO SIMULATOR</h1>'
    '<div class="subtitle">Resonant Modal Spectroscopy — Fracture Healing Assessment</div>'
    '</div>',
    unsafe_allow_html=True,
)

# === SIDEBAR CONTROLS ===
params = render_sidebar()

# === MAIN COMPUTATION ===
# Extract parameters
bone = params["bone"]
bone_profile = params["bone_profile"]
fracture_type = params["fracture_type"]
callus_pct = params["callus_pct"]
pressure_n = params["pressure_n"]
implant_loose = params["implant_loose"]
week = params["week"]
non_union = params["non_union"]
f_healthy = bone_profile["f_healthy"]

# Generate signals
scan_data = generate_scan_signal(
    callus_pct=callus_pct,
    f_healthy=f_healthy,
    implant_loose=implant_loose,
    pressure_n=pressure_n,
)

healthy_data = generate_healthy_reference(
    f_healthy=f_healthy,
    zeta_healthy=bone_profile["zeta_healthy"],
)

# Run spectral analysis
injured_analysis = full_spectral_analysis(scan_data["response"], scan_data["fs"])
healthy_analysis = full_spectral_analysis(healthy_data["response"], healthy_data["fs"])

# Extract key values
f_n = scan_data["f_n"]
zeta = scan_data["zeta"]
q_factor = scan_data["q_factor"]

# Get measured values from spectral analysis
if injured_analysis["primary_peak"]:
    measured_f_n = injured_analysis["primary_peak"]["freq"]
    measured_q = injured_analysis["primary_peak"].get("q_factor", q_factor)
    measured_bandwidth = injured_analysis["primary_peak"].get("bandwidth_hz", f_n / q_factor)
    measured_zeta = injured_analysis["primary_peak"].get("zeta_measured", zeta)
else:
    measured_f_n = f_n
    measured_q = q_factor
    measured_bandwidth = f_n / q_factor if q_factor > 0 else 100
    measured_zeta = zeta

mdf = injured_analysis["mdf"]

# Clinical metrics
tsi = compute_tsi(measured_f_n, f_healthy)
rust = compute_rust(tsi)
cortex_scores = compute_rust_cortex_scores(tsi)

has_secondary_peak = len(injured_analysis["peaks"]) > 1 and implant_loose

classification = classify_healing(
    tsi=tsi, zeta=measured_zeta,
    implant_loose=implant_loose,
    has_secondary_peak=has_secondary_peak,
    week=week,
)

# ML classification — uses the bundled 25-feature RandomForest model
ml_result = predict_healing_status(
    signal=scan_data["response"],
    fs=scan_data["fs"],
    f_healthy=f_healthy,
    callus_pct=callus_pct,
)

# Clinical summary
summary_text = generate_clinical_summary(
    bone=bone, fracture_type=fracture_type, week=week,
    tsi=tsi, f_n=measured_f_n, zeta=measured_zeta,
    q_factor=measured_q, classification=classification,
)

# === LAYOUT: 3-COLUMN ===
col_charts, col_metrics = st.columns([3, 1], gap="medium")

with col_charts:
    # --- PSD Comparison Chart (Hero) ---
    psd_fig = create_psd_chart(
        injured_psd=injured_analysis["psd"],
        healthy_psd=healthy_analysis["psd"],
        injured_peaks=injured_analysis["peaks"],
        healthy_peaks=healthy_analysis["peaks"],
        implant_loose=implant_loose,
        f_n_injured=measured_f_n,
        secondary_f_n=scan_data.get("secondary_f_n"),
    )
    st.plotly_chart(psd_fig, use_container_width=True, key="psd_chart")

    with st.expander("📊 PSD Analysis — What You're Seeing", expanded=False):
        st.markdown(get_psd_analysis(
            measured_f_n=measured_f_n, f_healthy=f_healthy, tsi=tsi,
            measured_q=measured_q, measured_zeta=measured_zeta,
            implant_loose=implant_loose, has_secondary_peak=has_secondary_peak,
            bone=bone,
        ))

    # --- Waveform + Spectrogram side by side ---
    wave_col, spec_col = st.columns(2)

    with wave_col:
        waveform_fig = create_waveform_chart(scan_data)
        st.plotly_chart(waveform_fig, use_container_width=True, key="waveform_chart")

        with st.expander("📈 Waveform Analysis", expanded=False):
            st.markdown(get_waveform_analysis(
                zeta=measured_zeta, f_n=measured_f_n, bone=bone,
            ))

    with spec_col:
        spectrogram_fig = create_spectrogram_chart(
            injured_analysis["spectrogram"],
            f_n=measured_f_n,
        )
        st.plotly_chart(spectrogram_fig, use_container_width=True, key="spectrogram_chart")

        with st.expander("🔥 Spectrogram Analysis", expanded=False):
            st.markdown(get_spectrogram_analysis(
                f_n=measured_f_n, bone=bone,
            ))

    # --- Healing Timeline ---
    timeline_fig = create_healing_timeline(
        current_week=week,
        callus_pct=callus_pct,
        non_union=non_union,
        f_healthy=f_healthy,
    )
    st.plotly_chart(timeline_fig, use_container_width=True, key="timeline_chart")

    with st.expander("📅 Healing Timeline Analysis", expanded=False):
        st.markdown(get_timeline_analysis(
            week=week, tsi=tsi, non_union=non_union,
            callus_pct=callus_pct,
        ))

with col_metrics:
    # --- Traffic Light ---
    render_traffic_light(classification)

    st.markdown("---")

    # --- ML Classification ---
    render_ml_prediction(ml_result)

    st.markdown("---")

    # --- Clinical Metrics ---
    render_metrics_panel(
        tsi=tsi, rust=rust, f_n=measured_f_n,
        zeta=measured_zeta, q_factor=measured_q,
        mdf=mdf, bandwidth=measured_bandwidth,
    )

    st.markdown("---")

    with st.expander("🩺 Classification & Decision Analysis", expanded=False):
        st.markdown(get_classification_analysis(
            classification=classification, ml_result=ml_result,
            implant_loose=implant_loose,
        ))

    with st.expander("🔢 Metrics Explained", expanded=False):
        st.markdown(get_metrics_analysis(
            tsi=tsi, rust=rust, measured_q=measured_q,
            measured_zeta=measured_zeta, mdf=mdf, bone=bone,
        ))

# === CLINICAL SUMMARY (FULL WIDTH) ===
render_clinical_summary(summary_text)

with st.expander("🧬 How ResoScan Technology Works", expanded=False):
    st.markdown(get_technology_explainer())

# === PDF REPORT DOWNLOAD ===
st.markdown("---")
report_col1, report_col2 = st.columns([3, 1])

with report_col2:
    report_params = {
        "bone": bone,
        "fracture_type": fracture_type,
        "week": week,
        "callus_pct": callus_pct,
        "pressure_n": pressure_n,
        "pressure_status": params["pressure_result"]["status"],
        "implant_loose": implant_loose,
    }
    report_metrics = {
        "tsi": tsi,
        "rust": rust,
        "f_n": measured_f_n,
        "zeta": measured_zeta,
        "q_factor": measured_q,
        "mdf": mdf,
        "bandwidth": measured_bandwidth,
        "cortex_scores": cortex_scores,
    }

    pdf_bytes = generate_report(
        params=report_params,
        metrics=report_metrics,
        classification=classification,
        ml_result=ml_result,
        summary_text=summary_text,
    )

    st.download_button(
        label="📄 Download Clinical Report (PDF)",
        data=pdf_bytes,
        file_name=f"ResoScan_Report_{bone}_{fracture_type}_Wk{week}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

with report_col1:
    # Scan info
    st.caption(
        f"Scan: {bone} | {fracture_type} | Week {week} | "
        f"Stiffness: {callus_pct}% | Pressure: {pressure_n:.1f}N | "
        f"{'Implant Loose' if implant_loose else 'No Implant'}"
    )
