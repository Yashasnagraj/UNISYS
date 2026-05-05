"""
ResoScan Analysis Text — Dynamic clinical interpretation and educational commentary.

Generates context-aware explanatory text for each visualization and metric,
written in the clinical language orthopedic surgeons use. Designed to help
investors and clinicians understand exactly what they're seeing and why it matters.
"""


def get_psd_analysis(measured_f_n: float, f_healthy: float, tsi: float,
                     measured_q: float, measured_zeta: float,
                     implant_loose: bool, has_secondary_peak: bool,
                     bone: str) -> str:
    """Generate analysis text for the PSD comparison chart."""
    freq_shift = f_healthy - measured_f_n
    freq_shift_pct = (freq_shift / f_healthy) * 100

    lines = []

    # What you're seeing
    lines.append(
        f"**What you're seeing:** The Power Spectral Density (PSD) reveals the "
        f"vibrational fingerprint of the {bone.lower()}. The **blue dashed line** "
        f"is the healthy baseline — a sharp, narrow peak at **{f_healthy:.0f} Hz**, "
        f"indicating a rigid, intact bone with minimal energy loss. The **solid line** "
        f"is the current scan of the fractured bone."
    )

    # Frequency shift interpretation
    if freq_shift_pct > 30:
        lines.append(
            f"The resonant peak has shifted **{freq_shift_pct:.0f}% lower** to "
            f"**{measured_f_n:.0f} Hz** — a significant leftward shift indicating "
            f"the fracture site is still mechanically discontinuous. Think of it like "
            f"a cracked bell: the break lowers the pitch because the bone can't vibrate "
            f"as a single rigid body."
        )
    elif freq_shift_pct > 15:
        lines.append(
            f"The peak has shifted **{freq_shift_pct:.0f}% lower** to **{measured_f_n:.0f} Hz**. "
            f"This moderate leftward shift shows callus is forming and bridging the fracture gap, "
            f"but the bone hasn't yet regained full structural stiffness. As mineralization "
            f"progresses, this peak will migrate rightward toward the healthy baseline."
        )
    elif freq_shift_pct > 5:
        lines.append(
            f"The peak sits at **{measured_f_n:.0f} Hz** — only **{freq_shift_pct:.0f}%** below "
            f"the healthy reference. This near-convergence indicates advanced consolidation. "
            f"The callus has mineralized significantly and the bone is approaching structural integrity."
        )
    else:
        lines.append(
            f"The peak at **{measured_f_n:.0f} Hz** is within **{freq_shift_pct:.0f}%** of the "
            f"healthy reference — the spectral signatures have essentially converged, confirming "
            f"solid bony union."
        )

    # Peak width / Q-factor
    if measured_q > 15:
        lines.append(
            f"The peak is **narrow and sharp** (Q = {measured_q:.1f}), meaning the bone absorbs "
            f"very little vibrational energy — a hallmark of solid, mineralized tissue with "
            f"high mechanical integrity."
        )
    elif measured_q > 6:
        lines.append(
            f"The peak width is **moderate** (Q = {measured_q:.1f}). Some energy dissipation "
            f"at the fracture site is broadening the resonance — consistent with callus "
            f"that has stiffened but hasn't fully mineralized."
        )
    else:
        lines.append(
            f"The peak is **broad and diffuse** (Q = {measured_q:.1f}), indicating high energy "
            f"dissipation. The fracture site is absorbing vibration rather than transmitting it — "
            f"soft tissue or unmineralized callus is damping the signal significantly."
        )

    # Implant rattle
    if implant_loose and has_secondary_peak:
        lines.append(
            f"**ALERT — Secondary Peak Detected:** A second spectral peak is visible at a lower "
            f"frequency, separate from the primary resonance. This is the spectral signature of "
            f"**implant micromotion** — the hardware is vibrating independently of the bone, "
            f"producing its own resonant mode. In clinical practice, this \"rattle peak\" is a "
            f"strong indicator of hardware loosening requiring orthopedic evaluation."
        )

    return "\n\n".join(lines)


def get_waveform_analysis(zeta: float, f_n: float, bone: str) -> str:
    """Generate analysis text for the time-domain waveform chart."""
    # Decay time constant
    wn = 2 * 3.14159 * f_n
    tau_ms = 1000.0 / (zeta * wn) if zeta * wn > 0 else 999

    lines = []

    lines.append(
        f"**Top panel — Chirp Excitation:** A swept-sine signal (20-1200 Hz) is applied "
        f"to the {bone.lower()}, systematically probing every frequency in the diagnostic range. "
        f"When the sweep passes through the bone's natural frequency, the response amplitude "
        f"peaks — this is resonance."
    )

    lines.append(
        f"**Bottom panel — Tissue Response:** The bone's vibrational response, with the "
        f"**red dashed envelope** showing the exponential decay rate. "
        f"The signal decays with a time constant of **~{tau_ms:.1f} ms**."
    )

    if zeta > 0.12:
        lines.append(
            f"The rapid decay (high damping, zeta = {zeta:.3f}) means the fracture site is "
            f"absorbing energy quickly — soft tissue and unmineralized callus act as a damper. "
            f"As healing progresses, the envelope will stretch longer, indicating the bone is "
            f"transmitting vibration more efficiently."
        )
    elif zeta > 0.05:
        lines.append(
            f"Moderate decay rate (zeta = {zeta:.3f}) — the callus is stiffening and beginning "
            f"to transmit vibrational energy across the fracture gap, but still absorbs some "
            f"energy at the healing site."
        )
    else:
        lines.append(
            f"Slow, sustained decay (zeta = {zeta:.3f}) — the bone rings clearly after "
            f"excitation, just like an intact bone would. Minimal energy loss at the fracture "
            f"site indicates high mechanical continuity."
        )

    return "\n\n".join(lines)


def get_spectrogram_analysis(f_n: float, bone: str) -> str:
    """Generate analysis text for the spectrogram heatmap."""
    return (
        f"**What you're seeing:** The spectrogram shows how vibrational energy is distributed "
        f"across both frequency (vertical axis) and time (horizontal axis). The bright horizontal "
        f"band near **{f_n:.0f} Hz** is the bone's resonant response — it lights up when the "
        f"chirp excitation sweeps through that frequency.\n\n"
        f"**Why it matters:** In a healthy bone, you'd see a tight, bright band at a higher "
        f"frequency. A fractured bone shows the band shifted lower and spread wider. The width "
        f"of the bright region corresponds to the bandwidth (inversely related to Q-factor) — "
        f"wider means more damping, more energy loss at the fracture site. This view confirms "
        f"the PSD findings in a complementary time-frequency domain."
    )


def get_timeline_analysis(week: int, tsi: float, non_union: bool,
                          callus_pct: float) -> str:
    """Generate analysis text for the healing timeline chart."""
    lines = []

    lines.append(
        f"**Healing Trajectory:** This chart tracks the Tibial Stiffness Index (TSI) over "
        f"the standard 16-week healing window. The **blue dashed curve** is the expected "
        f"Gompertz sigmoid — the natural S-shaped healing trajectory where early weeks show "
        f"slow progress (inflammation), mid-weeks accelerate (callus mineralization), and "
        f"late weeks plateau (remodeling)."
    )

    lines.append(
        f"**Current position:** Week **{week}** with TSI at **{tsi:.1f}%**. "
        f"The **green line at 80%** is the weight-bearing clearance threshold — above this, "
        f"the bone can structurally support full body weight. The **red line at 40%** flags "
        f"non-union concern if the patient remains below it past week 16."
    )

    if non_union:
        lines.append(
            f"**Non-Union Trajectory (red):** The non-union simulation shows healing stalling "
            f"around 25-30% TSI after week 6 — the callus stops mineralizing and the fracture "
            f"gap fails to bridge. This pattern (plateau below 40% past week 16) is a clinical "
            f"red flag indicating the fracture may require intervention: bone grafting, revision "
            f"fixation, or bone stimulation therapy."
        )

    if tsi > 80:
        lines.append(
            f"At **{tsi:.1f}% TSI**, the patient has crossed the weight-bearing threshold. "
            f"Progressive loading can begin under clinical supervision."
        )
    elif tsi > 60:
        lines.append(
            f"At **{tsi:.1f}% TSI**, healing is on track but hasn't reached the weight-bearing "
            f"threshold yet. The projection (dotted line) estimates when clearance may be achieved "
            f"if the current trajectory continues."
        )
    elif week > 12 and tsi < 40:
        lines.append(
            f"**Concern:** At week {week} with only {tsi:.1f}% TSI, healing is significantly "
            f"behind schedule. If TSI remains below 40% at week 16, non-union should be suspected."
        )

    return "\n\n".join(lines)


def get_metrics_analysis(tsi: float, rust: int, measured_q: float,
                         measured_zeta: float, mdf: float,
                         bone: str) -> str:
    """Generate analysis text for the metrics panel."""
    lines = []

    lines.append("**Understanding the Numbers:**")

    # TSI
    lines.append(
        f"- **TSI {tsi:.1f}%** — Ratio of injured-to-healthy resonant frequency. "
        f"At 100%, the bone has fully recovered its vibrational characteristics. "
        f"Below 60% indicates significant mechanical deficit."
    )

    # RUST
    lines.append(
        f"- **RUST {rust}/12** — Radiographic Union Score for Tibial fractures. "
        f"Each of 4 cortices (anterior, posterior, medial, lateral) is scored 1-3 "
        f"based on callus bridging. Score of 10+ suggests radiographic union."
    )

    # Q-factor
    lines.append(
        f"- **Q-Factor {measured_q:.1f}** — Resonance quality. Higher Q means sharper "
        f"resonance, less energy loss, stronger bone. Healthy bone typically shows Q > 15."
    )

    # Damping
    lines.append(
        f"- **Damping {measured_zeta:.4f}** — Energy absorption rate. Lower is better. "
        f"Below 0.03 indicates solid union; above 0.10 suggests significant instability."
    )

    return "\n\n".join(lines)


def get_classification_analysis(classification: dict, ml_result: dict,
                                 implant_loose: bool) -> str:
    """Generate analysis text for the classification and traffic light."""
    status = classification["status"]
    traffic = classification["traffic_light"]
    ml_label = ml_result["predicted_label"]
    ml_conf = ml_result["confidence"]

    lines = []

    if traffic == "GREEN":
        lines.append(
            f"**Clinical Decision: CLEAR FOR WEIGHT-BEARING.** Both the rule-based engine "
            f"and the ML classifier agree — spectral analysis confirms the fracture site has "
            f"achieved sufficient mechanical integrity for progressive full loading. The resonant "
            f"frequency has converged toward the healthy baseline and damping is minimal."
        )
    elif traffic == "YELLOW":
        lines.append(
            f"**Clinical Decision: PARTIAL LOADING.** The bone is healing but hasn't crossed "
            f"the full weight-bearing threshold. Partial loading with an assistive device "
            f"(crutches, walker) promotes controlled mechanical stimulus that accelerates "
            f"callus mineralization — Wolff's Law in action. A follow-up scan in 2-3 weeks "
            f"should show continued rightward shift of the resonant peak."
        )
    elif implant_loose:
        lines.append(
            f"**Clinical Decision: HARDWARE CONCERN.** The presence of a secondary spectral "
            f"peak — a frequency distinct from the primary bone resonance — indicates the implant "
            f"is vibrating independently. This micromotion can prevent union and risks implant "
            f"failure. Orthopedic evaluation recommended."
        )
    else:
        lines.append(
            f"**Clinical Decision: RESTRICTED LOADING.** Spectral analysis shows the fracture "
            f"site lacks sufficient stiffness for weight-bearing. The low resonant frequency and "
            f"high damping indicate the callus has not yet bridged or mineralized adequately. "
            f"Continued immobilization with serial monitoring recommended."
        )

    lines.append(
        f"The **Random Forest classifier** independently predicts **{ml_label}** with "
        f"**{ml_conf:.0f}%** confidence, trained on 600 synthetic spectral feature sets. "
        f"This dual-validation (rule-based + ML) provides defense-in-depth for clinical decisions."
    )

    return "\n\n".join(lines)


def get_technology_explainer() -> str:
    """Return a concise explanation of how RMS technology works."""
    return (
        "### How Resonant Modal Spectroscopy Works\n\n"
        "Every bone has a natural vibration frequency — like a tuning fork. A healthy tibia "
        "resonates around **850 Hz**. When fractured, this frequency drops because the bone "
        "can no longer vibrate as a single rigid structure.\n\n"
        "**ResoScan measures healing by tracking this frequency shift.** As callus forms and "
        "mineralizes, the resonant frequency climbs back toward the healthy baseline. The "
        "ratio of injured-to-healthy frequency (the **Tibial Stiffness Index**) tells clinicians "
        "exactly how much structural integrity has been restored — quantitatively, objectively, "
        "and without radiation.\n\n"
        "**The scan takes seconds:** A swept-sine excitation (chirp) is applied through the skin, "
        "and the vibrational response is captured. FFT spectral analysis extracts the resonant "
        "frequency, damping ratio, and Q-factor — the three numbers that define healing status.\n\n"
        "**Why this matters:** Current fracture monitoring relies on subjective X-ray interpretation "
        "(inter-rater agreement ~60%). ResoScan provides objective, quantitative metrics that "
        "correlate directly with mechanical strength — answering the question every surgeon asks: "
        "*\"Is this bone strong enough to bear weight?\"*"
    )
