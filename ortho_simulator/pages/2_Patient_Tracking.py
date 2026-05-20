"""
ResoScan — Patient Tracking & Days-to-Healing Prediction.

The clinical question: "Doctor, when can I walk?"

This page answers it. Load (or simulate) a patient's history of past
ResoScan device readings, fit a personalised Gompertz healing curve, and
project the date the patient will cross the TSI = 80% weight-bearing
threshold.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from data.demo_patients import (
    DEMO_PATIENTS, get_patient_names, get_patient, TODAY,
)
from engine.healing_prediction import (
    predict, fitted_curve_points, population_curve_points,
    TSI_TARGET_PCT, PRIOR_K, PRIOR_T0,
)
from ui.styles import get_custom_css


st.set_page_config(
    page_title="ResoScan — Patient Tracking",
    page_icon="📅",
    layout="wide",
)

# Apply the same dark medical theme as the main scan page
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Themed title bar matching the main page
st.markdown(
    '<div class="title-bar">'
    '<h1>WHEN CAN THIS PATIENT WALK?</h1>'
    '<div class="subtitle">Personalised healing trajectory and days-to-recovery prediction</div>'
    '</div>',
    unsafe_allow_html=True,
)
st.caption(
    "Pick a patient, see how their bone has been healing across all their "
    "ResoScan visits, and get a prediction of how many days until they're "
    "safe to walk without crutches."
)

# ============================================================================
#  Patient picker + demographic overrides
# ============================================================================

col_pick, col_demo = st.columns([2, 3])

with col_pick:
    st.subheader("Patient")
    patient_key = st.selectbox(
        "Select a patient from the demo registry",
        options=get_patient_names(),
        index=0,
    )

p = get_patient(patient_key)

with col_demo:
    st.subheader("Demographics & Fracture")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Age", f"{p['age']} yr")
    d2.metric("Sex", p["sex"])
    d3.metric("BMI", f"{p['bmi']:.1f}")
    d4.metric("Bone / Fracture", f"{p['bone']} / {p['fracture_type']}")

    d5, d6, d7, d8 = st.columns(4)
    d5.metric("Smoker", "Yes" if p["smoker"] else "No")
    d6.metric("Diabetic", "Yes" if p["diabetic"] else "No")
    d7.metric("Fracture date", p["fracture_date"].strftime("%d %b %Y"))
    d8.metric("Weeks post-fracture",
              f"{(TODAY - p['fracture_date']).days / 7.0:.1f}")

st.markdown("---")

# ============================================================================
#  Scan history table
# ============================================================================

st.subheader("Scan History from ResoScan Device")

scan_df = pd.DataFrame([
    {
        "Scan date": s["date"].strftime("%d %b %Y"),
        "Weeks since fracture": f"{s['week']:.1f}",
        "Bone resonance (Hz)": f"{s['f_n_hz']:.0f}",
        "Stiffness recovery (%)": f"{s['tsi_pct']:.1f}",
        "Vibration absorption": f"{s['zeta']:.3f}",
        "Verdict on the day": s["classification"],
    }
    for s in p["scans"]
])
st.dataframe(scan_df, use_container_width=True, hide_index=True)
st.caption(
    "**Stiffness recovery** is how stiff this patient's bone is right now, "
    "as a percentage of a healthy bone. **Vibration absorption** drops as "
    "the bone heals (a healthy bone barely absorbs the test vibration; a "
    "soft, healing bone absorbs a lot)."
)


# ============================================================================
#  Run prediction
# ============================================================================

scan_weeks = [s["week"] for s in p["scans"]]
scan_tsi   = [s["tsi_pct"] for s in p["scans"]]

pred = predict(
    scan_weeks=scan_weeks,
    scan_tsi=scan_tsi,
    fracture_date=p["fracture_date"],
    today=TODAY,
    smoker=p["smoker"],
    diabetic=p["diabetic"],
    age=p["age"],
)

st.markdown("---")
st.subheader("Personalised Healing Projection")

# Headline metric: estimated days to weight-bearing
result_color_map = {
    "ahead":  "#21c97a",   # green
    "on pace": "#f5b53d",  # amber
    "behind": "#e84a4a",   # red
}
pace_color = result_color_map.get(pred.pace_vs_population, "#888")

if pred.days_remaining is None:
    headline = (
        "Personal trajectory does not project to reach TSI 80% within a "
        "clinically reasonable window. Non-union risk."
    )
    headline_color = "#e84a4a"
    days_text = "—"
    date_text = "—"
elif pred.days_remaining == 0:
    headline = "Patient has already crossed the TSI 80% weight-bearing threshold."
    headline_color = "#21c97a"
    days_text = "0 days"
    date_text = "Cleared today"
else:
    headline = (
        f"Estimated time to full weight-bearing clearance: "
        f"**{pred.days_remaining} days** "
        f"(~{pred.weeks_remaining:.1f} weeks)"
    )
    headline_color = pace_color
    days_text = f"{pred.days_remaining} days"
    date_text = pred.target_date.strftime("%d %b %Y")

# Big banner
st.markdown(
    f"""
    <div style="
        background: linear-gradient(135deg, {headline_color}22, {headline_color}11);
        border-left: 6px solid {headline_color};
        padding: 1.2rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    ">
      <div style="font-size: 0.85rem; opacity:0.75; letter-spacing:0.08em;">
        ESTIMATED DAYS TO FULL WEIGHT-BEARING
      </div>
      <div style="font-size: 2.6rem; font-weight: 700; color:{headline_color};">
        {days_text}
      </div>
      <div style="font-size: 1.05rem; margin-top: 0.4rem;">
        Projected clearance date: <b>{date_text}</b>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Detail cards
m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "Current bone stiffness",
    f"{pred.current_tsi_pct:.0f}%",
    delta=f"{pred.current_tsi_pct - TSI_TARGET_PCT:+.0f}% vs walking-safe target",
    help="80% is the safe-to-walk threshold."
)
_pace_friendly = {
    "ahead":   "Healing faster than average",
    "on pace": "Healing at typical speed",
    "behind":  "Healing slower than average",
}.get(pred.pace_vs_population, pred.pace_vs_population.title())
m2.metric(
    "How fast is this patient healing?",
    _pace_friendly,
    delta=(f"{pred.pace_delta_days:+d} days vs average"
           if pred.pace_delta_days else "right on average"),
    delta_color=("inverse" if pred.pace_vs_population == "behind"
                 else "normal"),
)
_n_scans = len(scan_weeks)
m3.metric(
    "Scans on file",
    f"{_n_scans} scans",
    help="More scans = more confident the prediction.",
)
_conf_friendly = {
    "high":     "High confidence",
    "moderate": "Moderate confidence",
    "low":      "Low confidence (few scans yet)",
}.get(pred.confidence, pred.confidence.title())
m4.metric(
    "Prediction confidence",
    _conf_friendly,
    help="Confidence rises as we collect more scans from this patient.",
)


# ============================================================================
#  Trajectory chart
# ============================================================================

st.markdown("##### How the bone is healing over time")

# Window extends a couple of weeks beyond either the patient curve target
# or 20 weeks, whichever is larger.
max_week = max(20.0,
               (pred.weeks_to_target or 0) + 2.0,
               max(scan_weeks) + 2.0)

pop_weeks, pop_tsi = population_curve_points(max_week=max_week)
pat_weeks, pat_tsi = fitted_curve_points(pred, max_week=max_week)

fig = go.Figure()

# Population-average band
fig.add_trace(go.Scatter(
    x=pop_weeks, y=pop_tsi,
    mode="lines",
    name="What an average patient would look like",
    line=dict(color="#888", dash="dash", width=2),
    hovertemplate="Week %{x:.1f}<br>Average %{y:.1f}%<extra></extra>",
))

# Personalised fit
fig.add_trace(go.Scatter(
    x=pat_weeks, y=pat_tsi,
    mode="lines",
    name="This patient's predicted path",
    line=dict(color=headline_color, width=3),
    hovertemplate="Week %{x:.1f}<br>Predicted %{y:.1f}%<extra></extra>",
))

# Patient's actual scan points
fig.add_trace(go.Scatter(
    x=scan_weeks, y=scan_tsi,
    mode="markers+lines",
    name="Actual scan readings",
    marker=dict(size=12, color="#1f77b4",
                line=dict(color="white", width=2)),
    line=dict(color="#1f77b4", width=1),
    hovertemplate="Week %{x:.1f}<br>Measured %{y:.1f}%<extra></extra>",
))

# 80% target line
fig.add_hline(
    y=TSI_TARGET_PCT, line_dash="dot", line_color="#21c97a", line_width=2,
    annotation_text="Safe-to-walk threshold (80%)",
    annotation_position="top right",
    annotation_font_color="#21c97a",
)

# Mark the projected clearance week
if pred.weeks_to_target is not None and pred.weeks_to_target > 0:
    fig.add_vline(
        x=pred.weeks_to_target, line_dash="dot",
        line_color=headline_color, line_width=2,
        annotation_text=f"Expected clearance: week {pred.weeks_to_target:.1f}",
        annotation_position="bottom right",
        annotation_font_color=headline_color,
    )

# Mark current week
fig.add_vline(
    x=pred.current_week, line_color="#444", line_width=1,
    annotation_text=f"Today (week {pred.current_week:.1f})",
    annotation_position="top left",
)

fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0a0e17",
    plot_bgcolor="#0a0e17",
    xaxis_title="Weeks since the fracture happened",
    yaxis_title="Bone stiffness (% of healthy)",
    yaxis=dict(range=[0, 100], gridcolor="#1e293b"),
    xaxis=dict(gridcolor="#1e293b"),
    height=520,
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1,
                bgcolor="rgba(0,0,0,0)"),
    hovermode="x unified",
    font=dict(family="Inter, sans-serif", color="#f1f5f9"),
)

st.plotly_chart(fig, use_container_width=True)
st.caption(
    "Blue dots are the actual readings from the ResoScan device on each "
    "visit. The coloured line is the prediction of how this specific "
    "patient's bone will keep healing if nothing changes. The grey dashed "
    "line shows the average patient for comparison. Once a patient crosses "
    "the green 80% line, they're cleared to walk without crutches."
)


# ============================================================================
#  Clinical narrative
# ============================================================================

st.markdown("##### What to tell the patient")

risk_factors = []
if p["smoker"]:    risk_factors.append("smoking")
if p["diabetic"]:  risk_factors.append("diabetes")
if p["age"] >= 65: risk_factors.append("age over 65")
if risk_factors:
    risk_phrase = (
        f" Things slowing the healing down: {', '.join(risk_factors)}."
    )
else:
    risk_phrase = ""

if pred.days_remaining is None:
    narrative = (
        f"**{p['name']}'s** bone is healing far too slowly. After "
        f"**{pred.current_week:.0f} weeks** the bone has only recovered "
        f"**{pred.current_tsi_pct:.0f}%** of normal stiffness, and the "
        "healing has effectively stalled. At this pace the bone is unlikely "
        "to be safe to walk on within the next six months. "
        "**This is a non-union risk — refer to the orthopaedic surgeon "
        "for urgent review.** Options the surgeon may consider include a "
        f"bone-growth stimulator, revision surgery, or tests for vitamin / "
        f"hormone issues that might be holding back healing.{risk_phrase}"
    )
elif pred.days_remaining == 0:
    narrative = (
        f"**Good news for {p['name']}** — after "
        f"**{pred.current_week:.0f} weeks** the bone has reached "
        f"**{pred.current_tsi_pct:.0f}%** of normal stiffness. "
        "That clears the safe-to-walk threshold. "
        "**Cleared to walk without crutches.** "
        "Book one more ResoScan check in 4 weeks just to make sure the "
        "bone keeps getting stronger."
    )
else:
    pace_word = {
        "ahead":   "faster than typical",
        "on pace": "right on schedule",
        "behind":  "slower than typical",
    }.get(pred.pace_vs_population, "")
    narrative = (
        f"**{p['name']}** is healing **{pace_word}**. Based on the trend "
        f"across the last {len(scan_weeks)} scans, the bone should reach "
        f"the safe-to-walk point on "
        f"**{pred.target_date.strftime('%d %b %Y')}** — "
        f"about **{pred.days_remaining} days** from today "
        f"(~{pred.weeks_remaining:.0f} weeks). "
        "Until then: keep using crutches / brace as advised. "
        f"Book the next ResoScan in 2 weeks to check the trend.{risk_phrase}"
    )

st.markdown(narrative)

st.markdown("---")

# ============================================================================
#  Footer
# ============================================================================

st.caption(
    f"This prediction is based on **{len(scan_weeks)} scans** of this "
    f"specific patient. "
    f"Confidence: **{_conf_friendly.lower()}**. "
    "The safe-to-walk threshold (80% of healthy bone stiffness) is the "
    "standard used in published orthopaedic literature."
)
