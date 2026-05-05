"""
ResoScan Classification Panel — Traffic light + ML prediction + clinical summary.

Displays the clinical decision (GREEN/YELLOW/RED), ML classifier output
with confidence, and natural language clinical summary text.
"""

import streamlit as st
from ui.styles import traffic_light_html, badge_html


def render_traffic_light(classification: dict):
    """Render the traffic light clinical decision indicator.

    Args:
        classification: dict from clinical_metrics.classify_healing()
    """
    st.markdown('<div class="section-header">CLINICAL DECISION</div>',
                unsafe_allow_html=True)

    st.markdown(
        traffic_light_html(
            classification["status"],
            classification["color"],
            classification["traffic_light"],
        ),
        unsafe_allow_html=True,
    )

    st.markdown(f"**{classification['weight_bearing']}**")


def render_ml_prediction(ml_result: dict):
    """Render ML classifier prediction with confidence bar.

    Args:
        ml_result: dict from classification.predict_healing_status()
    """
    st.markdown('<div class="section-header">ML CLASSIFICATION</div>',
                unsafe_allow_html=True)

    label = ml_result["predicted_label"]
    confidence = ml_result["confidence"]

    # Color by prediction
    label_colors = {
        "Stable": "green",
        "Delayed Union": "yellow",
        "Non-Union": "red",
        "Implant Failure": "red",
    }
    color = label_colors.get(label, "cyan")

    st.markdown(
        badge_html(label, color),
        unsafe_allow_html=True,
    )

    st.markdown(f"**{confidence:.0f}%** confidence")

    # Confidence bar
    st.progress(confidence / 100.0)

    # Show all probabilities
    with st.expander("Class Probabilities"):
        for cls, prob in ml_result["probabilities"].items():
            st.markdown(f"**{cls}:** {prob:.1f}%")
            st.progress(prob / 100.0)


def render_clinical_summary(summary_text: str):
    """Render the natural language clinical summary.

    Args:
        summary_text: Generated clinical summary string
    """
    st.markdown(
        f'<div class="clinical-summary">'
        f'<strong>CLINICAL SUMMARY</strong><br><br>'
        f'{summary_text}'
        f'</div>',
        unsafe_allow_html=True,
    )
