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


st.set_page_config(
    page_title="ResoScan — Patient Tracking",
    page_icon="📅",
    layout="wide",
)

st.title("Patient Tracking & Days-to-Healing Prediction")
st.caption(
    "Personalised Gompertz curve fit on the patient's scan history. "
    "Projects the date they cross the TSI 80% full weight-bearing threshold."
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
        "Date": s["date"].strftime("%d %b %Y"),
        "Week": f"{s['week']:.1f}",
        "f₁ (Hz)": f"{s['f_n_hz']:.1f}",
        "TSI (%)": f"{s['tsi_pct']:.1f}",
        "ζ (damping)": f"{s['zeta']:.3f}",
        "Classification": s["classification"],
    }
    for s in p["scans"]
])
st.dataframe(scan_df, use_container_width=True, hide_index=True)


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
    "Current TSI",
    f"{pred.current_tsi_pct:.1f} %",
    delta=f"{pred.current_tsi_pct - TSI_TARGET_PCT:+.1f} vs target",
)
m2.metric(
    "Pace vs population",
    pred.pace_vs_population.title(),
    delta=f"{pred.pace_delta_days:+d} days" if pred.pace_delta_days else "0 days",
    delta_color=("inverse" if pred.pace_vs_population == "behind"
                 else "normal"),
)
m3.metric(
    "Fitted Gompertz rate k",
    f"{pred.fitted_k:.3f} /wk",
    delta=f"{(pred.fitted_k - PRIOR_K):+.3f} vs prior",
)
m4.metric(
    "Fit confidence",
    pred.confidence.title(),
    help="Confidence rises with more scans. >=4 scans = high.",
)


# ============================================================================
#  Trajectory chart
# ============================================================================

st.markdown("##### Healing trajectory")

# Window extends a couple of weeks beyond either the patient curve target
# or 20 weeks, whichever is larger.
max_week = max(20.0,
               (pred.weeks_to_target or 0) + 2.0,
               max(scan_weeks) + 2.0)

pop_weeks, pop_tsi = population_curve_points(max_week=max_week)
pat_weeks, pat_tsi = fitted_curve_points(pred, max_week=max_week)

fig = go.Figure()

# Population-average band (shaded)
fig.add_trace(go.Scatter(
    x=pop_weeks, y=pop_tsi,
    mode="lines",
    name="Population average",
    line=dict(color="#888", dash="dash", width=2),
    hovertemplate="Week %{x:.1f}<br>Pop TSI %{y:.1f}%<extra></extra>",
))

# Personalised fit
fig.add_trace(go.Scatter(
    x=pat_weeks, y=pat_tsi,
    mode="lines",
    name="Personal fit (Gompertz)",
    line=dict(color=headline_color, width=3),
    hovertemplate="Week %{x:.1f}<br>Personal TSI %{y:.1f}%<extra></extra>",
))

# Patient's actual scan points
fig.add_trace(go.Scatter(
    x=scan_weeks, y=scan_tsi,
    mode="markers+lines",
    name="Patient's scans",
    marker=dict(size=12, color="#1f77b4",
                line=dict(color="white", width=2)),
    line=dict(color="#1f77b4", width=1),
    hovertemplate="Week %{x:.1f}<br>Measured TSI %{y:.1f}%<extra></extra>",
))

# 80% target line
fig.add_hline(
    y=TSI_TARGET_PCT, line_dash="dot", line_color="#21c97a", line_width=2,
    annotation_text="Full weight-bearing threshold (TSI 80%)",
    annotation_position="top right",
    annotation_font_color="#21c97a",
)

# Mark the projected clearance week
if pred.weeks_to_target is not None and pred.weeks_to_target > 0:
    fig.add_vline(
        x=pred.weeks_to_target, line_dash="dot",
        line_color=headline_color, line_width=2,
        annotation_text=f"Projected clearance: week {pred.weeks_to_target:.1f}",
        annotation_position="bottom right",
        annotation_font_color=headline_color,
    )

# Mark current week
fig.add_vline(
    x=pred.current_week, line_color="#444", line_width=1,
    annotation_text=f"Now ({pred.current_week:.1f} wk)",
    annotation_position="top left",
)

fig.update_layout(
    xaxis_title="Weeks since fracture",
    yaxis_title="TSI (%)",
    yaxis=dict(range=[0, 100]),
    height=520,
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1),
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================================
#  Clinical narrative
# ============================================================================

st.markdown("##### Clinical recommendation")

risk_factors = []
if p["smoker"]:    risk_factors.append("smoker")
if p["diabetic"]:  risk_factors.append("diabetic")
if p["age"] >= 65: risk_factors.append("age ≥ 65")
risk_phrase = (
    f" Note risk factors: {', '.join(risk_factors)}." if risk_factors else ""
)

if pred.days_remaining is None:
    narrative = (
        f"**{p['name']}** is tracking well below the projected healing curve "
        f"with current TSI of **{pred.current_tsi_pct:.1f}%** at week "
        f"**{pred.current_week:.1f}**. The fitted personal Gompertz rate "
        f"(k = {pred.fitted_k:.3f}/wk) is insufficient to reach the 80% "
        "weight-bearing threshold within a clinically reasonable window. "
        "**Non-union risk — escalate to orthopaedic review.** Consider bone "
        "stimulator, revision surgery, or workup for metabolic / nutritional "
        f"causes of impaired union.{risk_phrase}"
    )
elif pred.days_remaining == 0:
    narrative = (
        f"**{p['name']}** has reached TSI {pred.current_tsi_pct:.1f}% at week "
        f"{pred.current_week:.1f} — at or above the 80% weight-bearing "
        "threshold. Cleared for **full weight-bearing**. Recommend a "
        "follow-up scan in 4 weeks to confirm sustained remodeling."
    )
else:
    narrative = (
        f"**{p['name']}** is tracking **{pred.pace_vs_population}** the "
        f"population-average healing curve. The personal Gompertz fit "
        f"(k = {pred.fitted_k:.3f}/wk, t₀ = {pred.fitted_t0:.1f} wk) "
        f"projects the patient will cross TSI 80% on "
        f"**{pred.target_date.strftime('%d %b %Y')}**, "
        f"approximately **{pred.days_remaining} days** from today. "
        "Until then: continue partial weight-bearing per current cast / "
        f"brace protocol. Next ResoScan recommended in 2 weeks.{risk_phrase}"
    )

st.markdown(narrative)

st.markdown("---")

# ============================================================================
#  Footer
# ============================================================================

st.caption(
    f"Personal fit: k = {pred.fitted_k:.3f} /wk, t₀ = {pred.fitted_t0:.2f} wk  •  "
    f"Population prior: k = {PRIOR_K} /wk, t₀ = {PRIOR_T0} wk  •  "
    f"Confidence: {pred.confidence}  •  "
    f"Scans fitted: {len(scan_weeks)}  •  "
    f"Threshold: TSI {TSI_TARGET_PCT:.0f}% (weight-bearing safety)"
)
