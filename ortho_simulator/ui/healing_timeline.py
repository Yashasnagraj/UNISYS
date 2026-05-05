"""
ResoScan Healing Timeline — 16-week progression chart.

Plotly line chart showing TSI progression over weeks with normal healing band,
threshold lines, and optional non-union trajectory overlay.
"""

import numpy as np
import plotly.graph_objects as go
from engine.healing_model import generate_healing_timeline, get_normal_healing_band


def create_healing_timeline(current_week: int, callus_pct: float,
                            non_union: bool = False,
                            f_healthy: float = 850.0) -> go.Figure:
    """Create the 16-week healing timeline chart.

    Args:
        current_week: Current week post-injury (0-16)
        callus_pct: Current callus stiffness for marker
        non_union: Whether to show non-union trajectory
        f_healthy: Healthy bone resonant frequency

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    # Normal healing band (±1 SD)
    band = get_normal_healing_band(17)
    fig.add_trace(go.Scatter(
        x=band["weeks"] + band["weeks"][::-1],
        y=band["upper"] + band["lower"][::-1],
        fill="toself",
        fillcolor="rgba(59, 130, 246, 0.08)",
        line=dict(width=0),
        name="Normal Range (±1 SD)",
        hoverinfo="skip",
    ))

    # Normal healing curve
    normal_timeline = generate_healing_timeline(17, non_union=False, f_healthy=f_healthy)
    normal_weeks = [d["week"] for d in normal_timeline]
    normal_tsi = [d["tsi"] for d in normal_timeline]

    fig.add_trace(go.Scatter(
        x=normal_weeks,
        y=normal_tsi,
        mode="lines",
        name="Expected Healing",
        line=dict(color="#3b82f6", width=2, dash="dash"),
        hovertemplate="Week %{x}<br>TSI: %{y:.1f}%<extra>Expected</extra>",
    ))

    # Non-union trajectory (if enabled)
    if non_union:
        nu_timeline = generate_healing_timeline(17, non_union=True, f_healthy=f_healthy)
        nu_weeks = [d["week"] for d in nu_timeline]
        nu_tsi = [d["tsi"] for d in nu_timeline]

        fig.add_trace(go.Scatter(
            x=nu_weeks,
            y=nu_tsi,
            mode="lines+markers",
            name="Non-Union Trajectory",
            line=dict(color="#ef4444", width=2.5),
            marker=dict(size=5, color="#ef4444"),
            hovertemplate="Week %{x}<br>TSI: %{y:.1f}%<extra>Non-Union</extra>",
        ))

    # Actual data points up to current week (using normal or non-union curve)
    actual_timeline = generate_healing_timeline(17, non_union=non_union, f_healthy=f_healthy)
    actual_weeks = [d["week"] for d in actual_timeline if d["week"] <= current_week]
    actual_tsi = [d["tsi"] for d in actual_timeline if d["week"] <= current_week]

    if not non_union:
        fig.add_trace(go.Scatter(
            x=actual_weeks,
            y=actual_tsi,
            mode="markers+lines",
            name="Measured TSI",
            line=dict(color="#06b6d4", width=2.5),
            marker=dict(size=7, color="#06b6d4", symbol="circle",
                        line=dict(width=1, color="#0a0e17")),
            hovertemplate="Week %{x}<br>TSI: %{y:.1f}%<extra>Measured</extra>",
        ))

    # Current position marker
    if actual_tsi:
        current_tsi = actual_tsi[-1]
        fig.add_trace(go.Scatter(
            x=[current_week],
            y=[current_tsi],
            mode="markers",
            name="Current",
            marker=dict(size=14, color="#f0f9ff", symbol="diamond",
                        line=dict(width=2, color="#06b6d4")),
            showlegend=False,
            hovertemplate=f"Week {current_week}<br>TSI: {current_tsi:.1f}%<extra>Current</extra>",
        ))

    # Projection line (dashed beyond current week)
    if current_week < 16:
        future_weeks = [d["week"] for d in actual_timeline if d["week"] >= current_week]
        future_tsi = [d["tsi"] for d in actual_timeline if d["week"] >= current_week]
        fig.add_trace(go.Scatter(
            x=future_weeks,
            y=future_tsi,
            mode="lines",
            name="Projection",
            line=dict(color="#06b6d4", width=1.5, dash="dot"),
            hoverinfo="skip",
        ))

    # Threshold lines
    fig.add_hline(
        y=80, line_dash="dash", line_color="#22c55e", opacity=0.6,
        annotation_text="Safe for WB (TSI > 80%)",
        annotation_font=dict(color="#22c55e", size=10),
        annotation_position="top right",
    )

    fig.add_hline(
        y=40, line_dash="dash", line_color="#ef4444", opacity=0.6,
        annotation_text="Non-Union Concern (TSI < 40%)",
        annotation_font=dict(color="#ef4444", size=10),
        annotation_position="bottom right",
    )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#111827",
        font=dict(family="JetBrains Mono, monospace", color="#f1f5f9", size=11),
        margin=dict(l=60, r=30, t=50, b=50),
        height=350,
        title=dict(
            text="Healing Timeline — TSI Progression",
            font=dict(size=14, color="#06b6d4"),
        ),
        xaxis=dict(
            title="Weeks Post-Injury",
            range=[-0.5, 16.5],
            dtick=2,
            gridcolor="#1e293b",
            zeroline=False,
        ),
        yaxis=dict(
            title="TSI (%)",
            range=[0, 110],
            gridcolor="#1e293b",
            zeroline=False,
        ),
        legend=dict(
            x=0.02, y=0.98,
            xanchor="left", yanchor="top",
            bgcolor="rgba(17, 24, 39, 0.8)",
            bordercolor="#1e293b",
            font=dict(size=10),
        ),
    )

    return fig
