"""
ResoScan Dark Medical Theme — Custom CSS for clinical-grade dashboard aesthetic.

Injected via st.markdown() for dark navy background, cyan accents,
monospace metric values, and medical instrument visual language.
"""


def get_custom_css() -> str:
    """Return the complete custom CSS for the ResoScan theme."""
    return """
    <style>
    /* === ROOT VARIABLES === */
    :root {
        --bg-primary: #0a0e17;
        --bg-card: #111827;
        --bg-card-hover: #1a2332;
        --border-subtle: #1e293b;
        --accent-cyan: #06b6d4;
        --accent-cyan-glow: rgba(6, 182, 212, 0.15);
        --signal-healthy: #3b82f6;
        --signal-injured: #ef4444;
        --safe-green: #22c55e;
        --caution-yellow: #eab308;
        --danger-red: #ef4444;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
    }

    /* === MAIN CONTAINER === */
    .stApp {
        background-color: var(--bg-primary) !important;
    }

    .main .block-container {
        padding-top: 1.5rem !important;
        max-width: 100% !important;
    }

    /* === SIDEBAR === */
    [data-testid="stSidebar"] {
        background-color: #0d1117 !important;
        border-right: 1px solid var(--border-subtle) !important;
    }

    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text-primary) !important;
    }

    /* === METRIC CARDS === */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 16px 20px;
        margin: 6px 0;
        transition: border-color 0.2s ease;
    }

    .metric-card:hover {
        border-color: var(--accent-cyan);
        box-shadow: 0 0 15px var(--accent-cyan-glow);
    }

    .metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-secondary);
        margin-bottom: 4px;
        font-family: 'Inter', sans-serif;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        color: var(--text-primary);
        line-height: 1.2;
    }

    .metric-unit {
        font-size: 0.85rem;
        color: var(--text-muted);
        margin-left: 4px;
    }

    /* === TRAFFIC LIGHT === */
    .traffic-light {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        border: 2px solid var(--border-subtle);
    }

    .traffic-green {
        border-color: var(--safe-green) !important;
        box-shadow: 0 0 20px rgba(34, 197, 94, 0.2);
    }

    .traffic-yellow {
        border-color: var(--caution-yellow) !important;
        box-shadow: 0 0 20px rgba(234, 179, 8, 0.2);
    }

    .traffic-red {
        border-color: var(--danger-red) !important;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
    }

    .traffic-label {
        font-size: 1rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        margin-top: 8px;
    }

    .traffic-circle {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        margin: 0 auto 10px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .circle-green { background: var(--safe-green); }
    .circle-yellow { background: var(--caution-yellow); }
    .circle-red { background: var(--danger-red); }

    /* === STATUS BADGES === */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .badge-green { background: rgba(34, 197, 94, 0.15); color: var(--safe-green); border: 1px solid var(--safe-green); }
    .badge-yellow { background: rgba(234, 179, 8, 0.15); color: var(--caution-yellow); border: 1px solid var(--caution-yellow); }
    .badge-red { background: rgba(239, 68, 68, 0.15); color: var(--danger-red); border: 1px solid var(--danger-red); }
    .badge-cyan { background: rgba(6, 182, 212, 0.15); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); }

    /* === PRESSURE GAUGE === */
    .pressure-bar {
        height: 8px;
        border-radius: 4px;
        background: var(--border-subtle);
        margin: 8px 0;
        overflow: hidden;
    }

    .pressure-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }

    /* === CLINICAL SUMMARY === */
    .clinical-summary {
        background: var(--bg-card);
        border: 1px solid var(--accent-cyan);
        border-left: 4px solid var(--accent-cyan);
        border-radius: 8px;
        padding: 16px 20px;
        margin: 16px 0;
        color: var(--text-primary);
        font-size: 0.9rem;
        line-height: 1.6;
    }

    /* === SECTION HEADERS === */
    .section-header {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: var(--accent-cyan);
        border-bottom: 1px solid var(--border-subtle);
        padding-bottom: 8px;
        margin: 20px 0 12px;
        font-weight: 600;
    }

    /* === RUST CORTEX GRID === */
    .cortex-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        margin: 8px 0;
    }

    .cortex-cell {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 6px;
        padding: 6px 10px;
        text-align: center;
        font-size: 0.75rem;
    }

    .cortex-1 { color: var(--danger-red); }
    .cortex-2 { color: var(--caution-yellow); }
    .cortex-3 { color: var(--safe-green); }

    /* === STREAMLIT OVERRIDES === */
    .stSelectbox label, .stSlider label, .stCheckbox label {
        color: var(--text-secondary) !important;
        font-size: 0.85rem !important;
    }

    /* st.metric — make readable on dark navy */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        padding: 10px 14px;
    }

    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        color: var(--text-primary) !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
        color: var(--text-secondary) !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }

    [data-testid="stMetricDelta"] {
        color: var(--text-muted) !important;
    }

    /* st.dataframe / st.table */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        background: var(--bg-card);
        border-radius: 8px;
        border: 1px solid var(--border-subtle);
    }

    [data-testid="stDataFrame"] div, [data-testid="stTable"] div {
        color: var(--text-primary);
    }

    /* st.expander */
    [data-testid="stExpander"] {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 8px;
    }
    [data-testid="stExpander"] summary {
        color: var(--text-primary) !important;
    }
    [data-testid="stExpander"] p {
        color: var(--text-secondary);
    }

    /* st.caption */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--text-muted) !important;
    }

    /* st.info / st.success / st.warning / st.error */
    [data-testid="stAlert"] {
        background: var(--bg-card) !important;
        border-left: 4px solid var(--accent-cyan) !important;
        color: var(--text-primary) !important;
    }

    /* Tables inside dataframes */
    .stDataFrame [role="row"]:nth-child(even) {
        background: rgba(255,255,255,0.02);
    }

    /* st.markdown body text on dark background */
    .stMarkdown, .stMarkdown p, .stMarkdown li {
        color: var(--text-secondary);
    }
    .stMarkdown strong {
        color: var(--text-primary);
    }
    .stMarkdown a {
        color: var(--accent-cyan);
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }

    /* st.selectbox dropdown closed state on dark */
    [data-baseweb="select"] > div {
        background: var(--bg-card) !important;
        border-color: var(--border-subtle) !important;
    }

    /* st.progress */
    [data-testid="stProgress"] > div > div {
        background: var(--accent-cyan) !important;
    }

    /* === TITLE BAR === */
    .title-bar {
        background: linear-gradient(135deg, #0d1117 0%, #111827 100%);
        border-bottom: 1px solid var(--accent-cyan);
        padding: 12px 20px;
        margin-bottom: 20px;
        border-radius: 8px;
    }

    .title-bar h1 {
        margin: 0 !important;
        font-size: 1.5rem !important;
        color: var(--accent-cyan) !important;
        letter-spacing: 0.05em;
    }

    .title-bar .subtitle {
        font-size: 0.8rem;
        color: var(--text-muted);
        margin-top: 2px;
    }

    /* === ML CONFIDENCE BAR === */
    .confidence-bar {
        height: 6px;
        border-radius: 3px;
        background: var(--border-subtle);
        margin: 6px 0;
        overflow: hidden;
    }

    .confidence-fill {
        height: 100%;
        border-radius: 3px;
        background: var(--accent-cyan);
    }

    /* === HIDE STREAMLIT DEFAULTS === */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """


def metric_card_html(label: str, value: str, unit: str = "",
                     color: str = "#f1f5f9") -> str:
    """Generate HTML for a styled metric card."""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color: {color};">
            {value}<span class="metric-unit">{unit}</span>
        </div>
    </div>
    """


def traffic_light_html(status: str, color: str, label: str) -> str:
    """Generate HTML for the traffic light indicator."""
    css_class = f"traffic-{color}"
    circle_class = f"circle-{color}"
    return f"""
    <div class="traffic-light {css_class}">
        <div class="traffic-circle {circle_class}"></div>
        <div class="traffic-label" style="color: {'#22c55e' if color == 'green' else '#eab308' if color == 'yellow' else '#ef4444'};">
            {status}
        </div>
    </div>
    """


def badge_html(text: str, color: str = "cyan") -> str:
    """Generate HTML for a status badge."""
    return f'<span class="badge badge-{color}">{text}</span>'


def pressure_gauge_html(pressure_n: float, status_color: str) -> str:
    """Generate HTML for the pressure gauge bar."""
    # Map 0-7N to 0-100% width
    pct = min(100, max(0, (pressure_n / 7.0) * 100))
    color_hex = "#22c55e" if status_color == "green" else "#eab308" if status_color == "yellow" else "#ef4444"
    return f"""
    <div class="pressure-bar">
        <div class="pressure-fill" style="width: {pct}%; background: {color_hex};"></div>
    </div>
    """


def cortex_grid_html(scores: dict) -> str:
    """Generate HTML for the RUST 4-cortex visual grid."""
    def cell(name, score):
        return f'<div class="cortex-cell cortex-{score}">{name}: {score}/3</div>'

    return f"""
    <div class="cortex-grid">
        {cell("Anterior", scores["anterior"])}
        {cell("Posterior", scores["posterior"])}
        {cell("Medial", scores["medial"])}
        {cell("Lateral", scores["lateral"])}
    </div>
    """
