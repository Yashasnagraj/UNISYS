"""
ResoScan Spectrogram Chart — Frequency-time heatmap visualization.

Displays the Short-Time Fourier Transform (STFT) as a 2D heatmap
showing how spectral energy evolves over the scan duration.
"""

import plotly.graph_objects as go


def create_spectrogram_chart(spectrogram_data: dict, f_n: float = 0) -> go.Figure:
    """Create frequency-time heatmap from STFT data.

    Args:
        spectrogram_data: dict from fft_engine.compute_spectrogram()
        f_n: Primary resonant frequency for annotation

    Returns:
        Plotly Figure with heatmap
    """
    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        z=spectrogram_data["magnitude_db"],
        x=spectrogram_data["times"] * 1000,  # Convert to ms
        y=spectrogram_data["frequencies"],
        colorscale=[
            [0.0, "#0a0e17"],
            [0.2, "#1e1b4b"],
            [0.4, "#312e81"],
            [0.6, "#4338ca"],
            [0.8, "#06b6d4"],
            [1.0, "#f0f9ff"],
        ],
        colorbar=dict(
            title=dict(text="dB", font=dict(size=11)),
            tickfont=dict(size=10),
            thickness=12,
            len=0.8,
        ),
        hovertemplate="Time: %{x:.1f} ms<br>Freq: %{y:.0f} Hz<br>Power: %{z:.1f} dB<extra></extra>",
    ))

    # Annotate primary resonant frequency
    if f_n > 0:
        fig.add_hline(
            y=f_n, line_dash="dot",
            line_color="#06b6d4", opacity=0.6,
            annotation_text=f"f₀ = {f_n:.0f} Hz",
            annotation_font_color="#06b6d4",
            annotation_font_size=10,
            annotation_position="top right",
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#111827",
        font=dict(family="JetBrains Mono, monospace", color="#f1f5f9", size=11),
        margin=dict(l=60, r=30, t=40, b=40),
        height=280,
        title=dict(
            text="Spectrogram — Frequency vs. Time",
            font=dict(size=13, color="#06b6d4"),
        ),
        xaxis=dict(
            title="Time (ms)",
            gridcolor="#1e293b",
        ),
        yaxis=dict(
            title="Frequency (Hz)",
            range=[0, 1200],
            gridcolor="#1e293b",
        ),
    )

    return fig
