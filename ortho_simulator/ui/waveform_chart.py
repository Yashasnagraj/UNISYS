"""
ResoScan Waveform Chart — Time-domain signal visualization.

Shows the raw excitation chirp and damped tissue response in the time domain,
with envelope decay visualization.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_waveform_chart(scan_data: dict) -> go.Figure:
    """Create time-domain waveform chart showing excitation and response.

    Args:
        scan_data: dict from signal_generator.generate_scan_signal()

    Returns:
        Plotly Figure with two subplots (excitation + response)
    """
    t = scan_data["t"] * 1000  # Convert to ms

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Chirp Excitation", "Tissue Response"),
        row_heights=[0.35, 0.65],
    )

    # Excitation chirp
    fig.add_trace(
        go.Scatter(
            x=t, y=scan_data["excitation"],
            mode="lines",
            name="Excitation",
            line=dict(color="#818cf8", width=1),
            hovertemplate="t: %{x:.1f} ms<br>Amp: %{y:.3f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # Response signal
    response = scan_data["response"]
    fig.add_trace(
        go.Scatter(
            x=t, y=response,
            mode="lines",
            name="Response",
            line=dict(color="#06b6d4", width=1.5),
            hovertemplate="t: %{x:.1f} ms<br>Amp: %{y:.4f}<extra></extra>",
        ),
        row=2, col=1,
    )

    # Envelope (exponential decay)
    zeta = scan_data["zeta"]
    f_n = scan_data["f_n"]
    wn = 2 * np.pi * f_n
    t_sec = scan_data["t"]
    envelope = np.max(np.abs(response)) * np.exp(-zeta * wn * t_sec)

    fig.add_trace(
        go.Scatter(
            x=t, y=envelope,
            mode="lines",
            name="Decay Envelope",
            line=dict(color="#ef4444", width=1.5, dash="dash"),
            hoverinfo="skip",
        ),
        row=2, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=t, y=-envelope,
            mode="lines",
            showlegend=False,
            line=dict(color="#ef4444", width=1.5, dash="dash"),
            hoverinfo="skip",
        ),
        row=2, col=1,
    )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#111827",
        font=dict(family="JetBrains Mono, monospace", color="#f1f5f9", size=11),
        margin=dict(l=60, r=30, t=40, b=40),
        height=320,
        showlegend=True,
        legend=dict(
            x=0.98, y=0.98,
            xanchor="right", yanchor="top",
            bgcolor="rgba(17, 24, 39, 0.8)",
            bordercolor="#1e293b",
            font=dict(size=10),
        ),
    )

    fig.update_xaxes(
        title_text="Time (ms)", row=2, col=1,
        gridcolor="#1e293b", zeroline=False,
    )
    fig.update_yaxes(gridcolor="#1e293b", zeroline=False)

    # Style subplot titles
    for annotation in fig.layout.annotations:
        annotation.font = dict(size=11, color="#94a3b8")

    return fig
