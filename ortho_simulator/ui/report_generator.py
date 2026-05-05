"""
ResoScan Report Generator — PDF clinical report export using fpdf2.

Generates a downloadable clinical report with scan parameters,
metrics, classification, and recommendations. Charts are embedded
as placeholders (full Plotly-to-PNG requires kaleido in production).
"""

import io
import datetime
from fpdf import FPDF


class ResoScanReport(FPDF):
    """Custom PDF class for ResoScan clinical reports."""

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(6, 182, 212)
        self.cell(0, 10, "ResoScan", border=False, align="L")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, "Resonant Modal Spectroscopy Report", border=False, align="R")
        self.ln(12)
        self.set_draw_color(30, 41, 59)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, "SIMULATION TOOL - NOT FOR CLINICAL DECISION-MAKING", align="C")
        self.ln(4)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(6, 182, 212)
        self.cell(0, 8, title, border=False)
        self.ln(2)
        self.set_draw_color(30, 41, 59)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def add_metric_row(self, label: str, value: str, unit: str = ""):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(148, 163, 184)
        self.cell(70, 7, label, border=False)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(241, 245, 249)
        self.cell(50, 7, f"{value} {unit}", border=False)
        self.ln(7)


def generate_report(params: dict, metrics: dict, classification: dict,
                    ml_result: dict, summary_text: str) -> bytes:
    """Generate a PDF clinical report.

    Args:
        params: Scan parameters (bone, fracture_type, callus_pct, etc.)
        metrics: Clinical metrics (tsi, rust, f_n, zeta, q_factor, etc.)
        classification: Healing classification result
        ml_result: ML prediction result
        summary_text: Natural language clinical summary

    Returns:
        PDF file as bytes
    """
    pdf = ResoScanReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    # Report metadata
    now = datetime.datetime.now()
    report_id = f"RSC-{now.strftime('%Y%m%d-%H%M%S')}"

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 5, f"Report ID: {report_id}  |  Generated: {now.strftime('%Y-%m-%d %H:%M')}  |  Facility: Demo Clinic", align="L")
    pdf.ln(8)

    # --- Patient & Scan Parameters ---
    pdf.section_title("SCAN PARAMETERS")

    pdf.add_metric_row("Bone", params.get("bone", "Tibia"))
    pdf.add_metric_row("Fracture Type", params.get("fracture_type", "Transverse"))
    pdf.add_metric_row("Week Post-Injury", str(params.get("week", 0)))
    pdf.add_metric_row("Callus Stiffness", f"{params.get('callus_pct', 0):.0f}", "%")
    pdf.add_metric_row("Contact Pressure", f"{params.get('pressure_n', 0):.1f}", "N")
    pdf.add_metric_row("Signal Quality", params.get("pressure_status", "OPTIMAL"))
    pdf.add_metric_row("Implant Status",
                       "LOOSE (simulated)" if params.get("implant_loose", False) else "N/A")

    # --- Clinical Metrics ---
    pdf.section_title("CLINICAL METRICS")

    pdf.add_metric_row("Tibial Stiffness Index (TSI)", f"{metrics.get('tsi', 0):.1f}", "%")
    pdf.add_metric_row("RUST Score", f"{metrics.get('rust', 4)}", "/ 12")
    pdf.add_metric_row("Resonant Frequency (f0)", f"{metrics.get('f_n', 0):.0f}", "Hz")
    pdf.add_metric_row("Damping Ratio (zeta)", f"{metrics.get('zeta', 0):.4f}")
    pdf.add_metric_row("Q-Factor", f"{metrics.get('q_factor', 0):.1f}")
    pdf.add_metric_row("Modal Damping (MDF)", f"{metrics.get('mdf', 0):.4f}")
    pdf.add_metric_row("-3dB Bandwidth", f"{metrics.get('bandwidth', 0):.1f}", "Hz")

    # --- RUST Cortex Breakdown ---
    if "cortex_scores" in metrics:
        cs = metrics["cortex_scores"]
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 6, "RUST Cortex Breakdown (1=No Callus, 2=Present, 3=Bridging):")
        pdf.ln(6)
        pdf.add_metric_row("  Anterior", f"{cs.get('anterior', 1)}", "/ 3")
        pdf.add_metric_row("  Posterior", f"{cs.get('posterior', 1)}", "/ 3")
        pdf.add_metric_row("  Medial", f"{cs.get('medial', 1)}", "/ 3")
        pdf.add_metric_row("  Lateral", f"{cs.get('lateral', 1)}", "/ 3")

    # --- Classification ---
    pdf.section_title("CLASSIFICATION & RECOMMENDATION")

    status = classification.get("status", "")
    traffic = classification.get("traffic_light", "")
    wb = classification.get("weight_bearing", "")

    pdf.set_font("Helvetica", "B", 12)
    color_map = {"GREEN": (34, 197, 94), "YELLOW": (234, 179, 8), "RED": (239, 68, 68)}
    rgb = color_map.get(traffic, (241, 245, 249))
    pdf.set_text_color(*rgb)
    pdf.cell(0, 10, f"[{traffic}] {status}")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(241, 245, 249)
    pdf.cell(0, 7, f"Weight-Bearing: {wb}")
    pdf.ln(10)

    # --- ML Prediction ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(6, 182, 212)
    pdf.cell(0, 7, f"ML Classification: {ml_result.get('predicted_label', 'N/A')} "
                    f"({ml_result.get('confidence', 0):.0f}% confidence)")
    pdf.ln(10)

    # --- Clinical Summary ---
    pdf.section_title("CLINICAL SUMMARY")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(241, 245, 249)
    pdf.multi_cell(0, 6, summary_text)
    pdf.ln(5)

    # --- Disclaimer ---
    pdf.ln(10)
    pdf.set_draw_color(239, 68, 68)
    pdf.set_fill_color(30, 20, 20)
    pdf.rect(10, pdf.get_y(), 190, 15, style="DF")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(239, 68, 68)
    pdf.set_xy(12, pdf.get_y() + 2)
    pdf.cell(0, 5, "DISCLAIMER", align="L")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.set_x(12)
    pdf.cell(0, 5, "This is a simulation tool for demonstration purposes only. "
                    "Not intended for clinical decision-making or patient care.", align="L")

    # Output
    pdf_bytes = pdf.output()
    return bytes(pdf_bytes)
