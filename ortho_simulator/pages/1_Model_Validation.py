"""
ResoScan — Model Validation page.

Renders the ML training methodology, cross-validation results, and
performance artifacts for the deployed classifier. Static PNG artifacts
are loaded from ml/artifacts/ (generated offline by train_model.py and
committed to the repo, so this page does not depend on kaleido at runtime).
"""

import os
import sys
import json

# Add parent so 'engine', 'ml', 'ui' imports work in Streamlit multipage
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ml.feature_extractor import FEATURE_NAMES
from ml.generate_dataset import LABEL_NAMES


HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(os.path.dirname(HERE), "ml", "artifacts")
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")

METRICS_PATH = os.path.join(ARTIFACTS_DIR, "metrics.json")
TRAIN_CSV    = os.path.join(DATA_DIR, "training_dataset.csv")
VAL_CSV      = os.path.join(DATA_DIR, "validation_dataset.csv")


st.set_page_config(
    page_title="ResoScan — Model Validation",
    page_icon="📊",
    layout="wide",
)

st.title("Model Validation & Methodology")
st.caption(
    "Cross-validated performance, dataset provenance, and methodology for the "
    "Random Forest classifier driving the ResoScan healing-state prediction."
)


# ============================================================================
#  Load metrics
# ============================================================================

if not os.path.exists(METRICS_PATH):
    st.error(
        f"Metrics not found at `{METRICS_PATH}`. "
        "Run `python ortho_simulator/ml/train_model.py` to generate."
    )
    st.stop()

with open(METRICS_PATH, "r", encoding="utf-8") as f:
    M = json.load(f)


# ============================================================================
#  Top headline cards
# ============================================================================

cv_best = M["cv_best"]
holdout = M["holdout"]
ext_val = M.get("external_validation") or {}

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Best model",
    cv_best["model"],
)
col2.metric(
    "CV F1-macro",
    f"{cv_best['f1_macro_mean']*100:.1f}%",
    f"±{cv_best['f1_macro_std']*100:.2f}%",
)
col3.metric(
    "Holdout accuracy",
    f"{holdout['accuracy']*100:.1f}%",
)
col4.metric(
    "External validation",
    f"{ext_val.get('accuracy', 0)*100:.1f}%" if ext_val else "—",
)


st.markdown("---")

# ============================================================================
#  Dataset summary
# ============================================================================

st.subheader("1. Dataset")

ds_c1, ds_c2 = st.columns([2, 3])

with ds_c1:
    st.markdown(
        f"""
- **Training samples**: {M['n_train_samples']:,}
- **Holdout samples**: {M['n_holdout_samples']:,}
- **Features per sample**: {M['n_features']}
- **Classes**: {len(M['labels'])}
- **Generation**: full signal pipeline
  `generate_scan_signal → FFT → feature_extractor`,
  identical to inference path.
        """
    )

with ds_c2:
    if os.path.exists(TRAIN_CSV):
        df_train = pd.read_csv(TRAIN_CSV, usecols=["label_name"])
        counts = df_train["label_name"].value_counts().reindex(LABEL_NAMES)
        fig = go.Figure(go.Bar(
            x=counts.index, y=counts.values,
            marker_color=["#2ca02c", "#ff7f0e", "#d62728", "#9467bd"],
            text=counts.values, textposition="outside",
        ))
        fig.update_layout(
            title="Training set class distribution",
            xaxis_title="", yaxis_title="Samples",
            height=320, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


with st.expander("Feature schema (25 engineered features)"):
    cols = st.columns(2)
    half = (len(FEATURE_NAMES) + 1) // 2
    cols[0].markdown(
        "\n".join(f"- `{f}`" for f in FEATURE_NAMES[:half])
    )
    cols[1].markdown(
        "\n".join(f"- `{f}`" for f in FEATURE_NAMES[half:])
    )

st.markdown("---")


# ============================================================================
#  CV results table
# ============================================================================

st.subheader("2. Cross-Validation Results")

cv_rows = []
for name, res in M["cv_results"].items():
    cv_rows.append({
        "Model": name,
        "F1-macro (mean)": f"{res['f1_macro_mean']*100:.2f}%",
        "F1-macro (std)":  f"±{res['f1_macro_std']*100:.2f}%",
        "Accuracy (mean)": f"{res['accuracy_mean']*100:.2f}%",
        "Accuracy (std)":  f"±{res['accuracy_std']*100:.2f}%",
        "Selected": "★" if name == cv_best["model"] else "",
    })
st.dataframe(pd.DataFrame(cv_rows), use_container_width=True, hide_index=True)

st.caption(
    "5-fold stratified cross-validation, stratification preserves class "
    "proportions across folds. Model selection by mean F1-macro on training "
    "split only (no leakage into holdout)."
)

st.markdown("---")


# ============================================================================
#  Performance artifacts (PNGs)
# ============================================================================

st.subheader("3. Performance Artifacts")

art_c1, art_c2 = st.columns(2)

cm_path = os.path.join(ARTIFACTS_DIR, "confusion_matrix.png")
roc_path = os.path.join(ARTIFACTS_DIR, "roc_curves.png")
fi_path = os.path.join(ARTIFACTS_DIR, "feature_importance.png")
lc_path = os.path.join(ARTIFACTS_DIR, "learning_curve.png")

with art_c1:
    if os.path.exists(cm_path):
        st.image(cm_path, caption="Confusion matrix (holdout set)",
                 use_container_width=True)
    if os.path.exists(fi_path):
        st.image(fi_path, caption="Feature importance",
                 use_container_width=True)

with art_c2:
    if os.path.exists(roc_path):
        st.image(roc_path, caption="ROC curves (one-vs-rest)",
                 use_container_width=True)
    if os.path.exists(lc_path):
        st.image(lc_path, caption="Learning curve",
                 use_container_width=True)


st.markdown("---")


# ============================================================================
#  Per-class breakdown
# ============================================================================

st.subheader("4. Per-Class Performance (Holdout)")

per_class = holdout["per_class"]
rows = []
for label in LABEL_NAMES:
    pc = per_class[label]
    rows.append({
        "Class": label,
        "Precision": f"{pc['precision']:.3f}",
        "Recall":    f"{pc['recall']:.3f}",
        "F1":        f"{pc['f1']:.3f}",
        "Support":   pc["support"],
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.caption(
    "Per-class precision/recall/F1 on the 20% holdout. Note that Delayed "
    "Union is intentionally the hardest class — it is the boundary state "
    "between Stable and Non-Union and we deliberately let class boundaries "
    "overlap during dataset generation so the model has to learn rather "
    "than memorize parameter ranges."
)


st.markdown("---")


# ============================================================================
#  Methodology
# ============================================================================

st.subheader("5. Methodology & Provenance")

st.markdown(
    """
**Why synthetic data is methodologically defensible**

No public dataset of bone vibrational responses during fracture healing
exists — this is novel sensor research. Our synthetic corpus is generated
by running the **production signal pipeline** itself
(`signal_generator → fft_engine → feature_extractor`),
so the training distribution matches the inference distribution exactly.

The pipeline is grounded in the **damped harmonic oscillator model** of
fracture healing (Pelker 1983; Cunningham 1990; Nakatsuchi 1996):
stiffness $k$ recovers along a Gompertz trajectory during the
hematoma → soft callus → hard callus → remodeling cascade, with
fundamental resonant frequency $f_1 \\propto \\sqrt{k/m}$ tracking that
recovery.

Class boundaries are deliberately **fuzzy with overlap** so the classifier
has to learn the underlying feature structure, not memorize disjoint
parameter ranges.

**Cross-domain validation**

The methodology aligns with peer-reviewed vibration-based damage
detection in analogous structural-health monitoring (SHM) domains where
the underlying physics — resonance shift and damping increase with damage
— is identical:
"""
)

st.markdown(
    """
- **Mendeley `n35zwbzhcf`** — Vibration data for laminated composite
  structures, healthy and delamination states.
- **Kaggle — Accelerometer Data, Steel Bridge Damage States** — multi-class
  damage classification on accelerometer data; direct problem-template
  analogue.
- **Kaggle — Building Structural Health Sensor Dataset** — multi-state
  SHM classification.
- **Mendeley `d3by55pjh7`** — Bridge vibration monitoring.
- **Kaggle — Cable Multi-State Monitoring System** — vibration + strain.
- **PhysioNet Respiratory Sound Database** — proxy validation for the
  pneumothorax / pulmonology branch of ResoScan.
"""
)

st.info(
    "**Roadmap to clinical data**: once IRB approval is in place, real "
    "patient-derived spectral profiles will replace the synthetic corpus. "
    "Because the feature schema and pipeline are unchanged between "
    "synthetic and real data, the production model can be retrained without "
    "re-engineering."
)


st.markdown("---")


# ============================================================================
#  Footer
# ============================================================================

st.caption(
    f"Model trained at {M.get('trained_at', 'unknown')}  •  "
    f"Best estimator: {cv_best['model']}  •  "
    f"Synthetic corpus: {M['n_train_samples']:,} samples × "
    f"{M['n_features']} features"
)
