"""
ResoScan PSD Comparison Chart — Hero visualization with healthy overlay.

Plotly figure showing Power Spectral Density comparison between
healthy reference and injured/healing bone, with peak annotations,
shaded difference region, and optional implant rattle secondary peak.
"""

import numpy as np
import plotly.graph_objects as go


PLOT_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0e17",
    plot_bgcolor="#111827",
    font=dict(family="JetBrains Mono, monospace", color="#f1f5f9"),
    margin=dict(l=60, r=30, t=50, b=50),
    height=420,
)


def create_psd_chart(injured_psd: dict, healthy_psd: dict,
                     injured_peaks: list, healthy_peaks: list,
                     implant_loose: bool = False,
                     f_n_injured: float = 0,
                     secondary_f_n: float = None) -> go.Figure:
    """Create the hero PSD comparison chart.

    Args:
        injured_psd: dict with freqs, psd_db from fft_engine
        healthy_psd: dict with freqs, psd_db from fft_engine
        injured_peaks: list of peak dicts from fft_engine
        healthy_peaks: list of peak dicts from fft_engine
        implant_loose: whether to annotate secondary peak
        f_n_injured: primary resonant frequency
        secondary_f_n: secondary (rattle) frequency if implant loose

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    # Limit frequency range to 0-1600 Hz
    freq_mask_h = healthy_psd["freqs"] <= 1600
    freq_mask_i = injured_psd["freqs"] <= 1600

    h_freqs = healthy_psd["freqs"][freq_mask_h]
    h_psd = healthy_psd["psd_db"][freq_mask_h]
    i_freqs = injured_psd["freqs"][freq_mask_i]
    i_psd = injured_psd["psd_db"][freq_mask_i]

    # Shaded difference region (where injured < healthy)
    min_len = min(len(h_psd), len(i_psd))
    shared_freqs = h_freqs[:min_len]
    h_shared = h_psd[:min_len]
    i_shared = i_psd[:min_len]

    fig.add_trace(go.Scatter(
        x=np.concatenate([shared_freqs, shared_freqs[::-1]]),
        y=np.concatenate([h_shared, i_shared[::-1]]),
        fill="toself",
        fillcolor="rgba(6, 182, 212, 0.08)",
        line=dict(width=0),
        name="Spectral Shift",
        showlegend=False,
        hoverinfo="skip",
    ))

    # Healthy reference (blue dashed)
    fig.add_trace(go.Scatter(
        x=h_freqs,
        y=h_psd,
        mode="lines",
        name="Healthy Reference",
        line=dict(color="#3b82f6", width=2, dash="dash"),
        hovertemplate="Freq: %{x:.0f} Hz<br>PSD: %{y:.1f} dB/Hz<extra>Healthy</extra>",
    ))

    # Injured/healing signal (cyan solid)
    injured_color = "#ef4444" if f_n_injured < 500 else "#06b6d4"
    fig.add_trace(go.Scatter(
        x=i_freqs,
        y=i_psd,
        mode="lines",
        name="Current Scan",
        line=dict(color=injured_color, width=2.5),
        hovertemplate="Freq: %{x:.0f} Hz<br>PSD: %{y:.1f} dB/Hz<extra>Injured</extra>",
    ))

    # Peak annotations — healthy
    if healthy_peaks:
        hp = healthy_peaks[0]
        fig.add_annotation(
            x=hp["freq"], y=hp["amplitude_db"],
            text=f'f₀ = {hp["freq"]:.0f} Hz (Healthy)',
            showarrow=True, arrowhead=2, arrowcolor="#3b82f6",
            font=dict(size=11, color="#3b82f6"),
            ax=40, ay=-40,
        )

    # Peak annotations — injured primary
    if injured_peaks:
        ip = injured_peaks[0]
        fig.add_annotation(
            x=ip["freq"], y=ip["amplitude_db"],
            text=f'f₀ = {ip["freq"]:.0f} Hz',
            showarrow=True, arrowhead=2, arrowcolor=injured_color,
            font=dict(size=12, color=injured_color, family="JetBrains Mono"),
            ax=-50, ay=-35,
        )

        # Vertical line at peak
        fig.add_vline(
            x=ip["freq"], line_dash="dot",
            line_color=injured_color, opacity=0.4,
        )

    # Secondary peak (implant rattle)
    if implant_loose and secondary_f_n and len(injured_peaks) > 1:
        sp = injured_peaks[1] if len(injured_peaks) > 1 else None
        if sp:
            fig.add_annotation(
                x=sp["freq"], y=sp["amplitude_db"],
                text="Secondary Harmonic<br>Implant Rattle",
                showarrow=True, arrowhead=2, arrowcolor="#ef4444",
                font=dict(size=10, color="#ef4444"),
                ax=50, ay=-50,
                bordercolor="#ef4444", borderwidth=1, borderpad=4,
                bgcolor="rgba(239, 68, 68, 0.1)",
            )
    elif implant_loose and secondary_f_n:
        # Mark expected secondary location even if peak detection didn't find it
        fig.add_vline(
            x=secondary_f_n, line_dash="dot",
            line_color="#ef4444", opacity=0.5,
            annotation_text="Rattle",
            annotation_font_color="#ef4444",
        )

    # Layout
    fig.update_layout(
        **PLOT_LAYOUT,
        title=dict(
            text="Power Spectral Density — Bone Resonance Comparison",
            font=dict(size=14, color="#06b6d4"),
        ),
        xaxis=dict(
            title="Frequency (Hz)",
            range=[0, 1600],
            gridcolor="#1e293b",
            zeroline=False,
        ),
        yaxis=dict(
            title="PSD (dB/Hz)",
            gridcolor="#1e293b",
            zeroline=False,
        ),
        legend=dict(
            x=0.98, y=0.98,
            xanchor="right", yanchor="top",
            bgcolor="rgba(17, 24, 39, 0.8)",
            bordercolor="#1e293b",
        ),
    )

    return fig
