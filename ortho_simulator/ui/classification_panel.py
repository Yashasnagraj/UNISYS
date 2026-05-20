"""
ResoScan Classification Panel — Traffic light + ML prediction + clinical summary.

Displays the clinical decision (GREEN/YELLOW/RED), ML classifier output
with confidence, and natural language clinical summary text.
"""

import json
import os

import streamlit as st
from ui.styles import traffic_light_html, badge_html


# Lazily load training-time metrics so the panel can show CV-validated
# accuracy alongside the runtime prediction. Streamlit's cache keeps this
# in memory across reruns.
_METRICS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ml", "artifacts", "metrics.json",
)


@st.cache_data
def _load_validation_metrics() -> dict:
    if not os.path.exists(_METRICS_PATH):
        return {}
    try:
        with open(_METRICS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# Plain-English names for the 25 engineered features. Used in the
# "Why this assessment?" expander so non-technical users can read the
# explanation without a signal-processing degree.
_FEATURE_FRIENDLY = {
    "f_peak": "Strongest vibration frequency",
    "A_peak": "How strong the main vibration is",
    "spectral_centroid": "Where the average vibration energy sits",
    "spectral_bandwidth": "How wide the main resonance is",
    "spectral_rolloff_85": "Where most of the vibration energy concentrates",
    "spectral_flatness": "How clear vs noisy the resonance is",
    "q_factor": "How sharp the resonance is (sharper = stiffer bone)",
    "band_energy_low": "Energy in the low-frequency band",
    "band_energy_mid": "Energy in the mid-frequency band",
    "band_energy_high": "Energy in the high-frequency band",
    "peak_splitting_flag": "Is there a second resonance? (often loose hardware)",
    "secondary_peak_ratio": "Strength of the second resonance vs the main one",
    "rms_amplitude": "Overall vibration intensity",
    "peak_to_peak": "Largest swing in the vibration",
    "crest_factor": "How spiky vs smooth the vibration is",
    "zero_crossing_rate": "How often the signal crosses zero",
    "decay_time_ms": "How quickly the vibration fades away",
    "signal_kurtosis": "How peaky the vibration shape is",
    "signal_skew": "Whether the vibration leans up or down",
    "damping_ratio": "How quickly the bone absorbs vibration energy",
    "log_decrement": "Rate at which the vibration dies out",
    "half_power_bandwidth": "Width of the resonance at half its strength",
    "mdf": "Overall energy loss as the bone vibrates",
    "tsi": "Bone stiffness as a percentage of healthy",
    "callus_proxy": "Estimated stage of callus formation",
}


def _format_friendly_value(name: str, value: float) -> str:
    """Format a feature value in user-friendly units."""
    if name == "tsi":
        return f"currently at **{value:.1f}%** of healthy"
    if name == "f_peak" or name == "spectral_centroid" or name == "spectral_rolloff_85":
        return f"around **{value:.0f} Hz**"
    if name == "damping_ratio":
        return f"value: **{value:.3f}** (lower means stiffer)"
    if name == "q_factor":
        return f"value: **{value:.1f}** (higher means stiffer)"
    if name == "peak_splitting_flag":
        return "**yes**" if value >= 0.5 else "**no**"
    if name == "decay_time_ms":
        return f"about **{value:.0f} ms** to fade"
    if name.startswith("band_energy"):
        return f"around **{value*100:.0f}%** of the total signal energy"
    return f"value: **{value:.3f}**"


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
    st.markdown('<div class="section-header">AI HEALING ASSESSMENT</div>',
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

    st.markdown(f"**{confidence:.0f}%** sure")

    # Confidence bar
    st.progress(confidence / 100.0)

    # Show all probabilities — plain-English label
    with st.expander("Other possible outcomes the AI considered"):
        st.caption(
            "How likely the AI thinks each outcome is, based on this scan."
        )
        for cls, prob in ml_result["probabilities"].items():
            st.markdown(f"**{cls}:** {prob:.1f}%")
            st.progress(prob / 100.0)

    # --- Trust badge (plain English) ---
    # Shows the same accuracy number the Model Validation page proves in
    # detail, so any user can see "this isn't a guess" without needing to
    # know what RandomForest or cross-validation means.
    metrics = _load_validation_metrics()
    cv_best = metrics.get("cv_best", {})
    cv_acc = cv_best.get("accuracy_mean")
    n_train = metrics.get("n_train_samples")

    if cv_acc is not None:
        n_text = f"{n_train:,}" if n_train else "thousands of"
        badge = (
            f"<div style='"
            f"margin-top:0.6rem; padding:0.6rem 0.8rem;"
            f"border-left:3px solid #21c97a; background:rgba(33,201,122,0.10);"
            f"border-radius:6px; font-size:0.82rem; line-height:1.5;'>"
            f"<div style='opacity:0.75; letter-spacing:0.05em; font-size:0.72rem;'>"
            f"HOW RELIABLE IS THIS?</div>"
            f"<div style='margin-top:0.2rem;'>"
            f"The assessment AI has been tested against <b>{n_text}</b> "
            f"healing cases and gives the correct verdict "
            f"<b>{cv_acc*100:.0f}% of the time</b>."
            f"</div>"
            f"<div style='margin-top:0.3rem; opacity:0.85;'>"
            f"Open the <b>Model Validation</b> page for the full accuracy "
            f"breakdown and how it was tested."
            f"</div>"
            f"</div>"
        )
        st.markdown(badge, unsafe_allow_html=True)

    # --- "Why this assessment?" (plain-English feature explanations) ---
    top_features = ml_result.get("top_features") or []
    if top_features:
        with st.expander("Why this assessment?"):
            st.caption(
                "These are the three measurements the assessment leaned on "
                "most for this scan, in order of how much they influenced "
                "the result."
            )
            for f in top_features:
                description = _FEATURE_FRIENDLY.get(
                    f["name"],
                    f["name"].replace("_", " "),
                )
                value = _format_friendly_value(f["name"], f["value"])
                st.markdown(
                    f"- **{description}** &mdash; {value}",
                    unsafe_allow_html=True,
                )


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
