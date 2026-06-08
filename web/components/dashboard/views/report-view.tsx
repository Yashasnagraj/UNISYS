"use client";

/**
 * Compliance Report — printable clinical document.
 *
 * All numeric values shown here come DIRECTLY from the backend normalization
 * pipeline (f_peak_hz, tsi_pct, zeta, improvement_factor, etc.).
 * Nothing is hardcoded or estimated. If a value is null it shows "—".
 *
 * Print: window.print() with a @media print stylesheet that hides chrome.
 */

import { useEffect, useState } from "react";
import { FileText, Printer, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ApiPatient, ApiScanDetail, ApiRepeatability } from "@/lib/api";
import { api } from "@/lib/api";
import { ScanHistoryTable } from "@/components/dashboard/scan-history-table";
import { InfoTip } from "@/components/ui/info-tip";

// ── helpers ────────────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, decimals = 1, unit = ""): string {
  if (v == null) return "—";
  return v.toFixed(decimals) + (unit ? " " + unit : "");
}

function trafficLabel(t: string | null) {
  if (t === "green") return { label: "CLEARED", color: "var(--safe)" };
  if (t === "amber") return { label: "CAUTION — DELAYED UNION", color: "var(--caution)" };
  return { label: "RISK — REFER SURGEON", color: "var(--danger)" };
}

// ── TSI gauge (SVG arc) ────────────────────────────────────────────────────────

function TsiGauge({ tsi, trafficLight }: { tsi: number | null; trafficLight: string | null }) {
  const val = tsi ?? 0;
  const color =
    trafficLight === "green" ? "var(--safe)"
    : trafficLight === "amber" ? "var(--caution)"
    : "var(--danger)";

  // Arc from 210° to 330° (240° sweep)
  const R = 52, cx = 70, cy = 70;
  const startDeg = 210, sweepDeg = 240;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const pct = Math.min(1, Math.max(0, val / 100));
  const endDeg = startDeg + pct * sweepDeg;

  function arcPath(start: number, end: number, r: number) {
    const s = { x: cx + r * Math.cos(toRad(start)), y: cy + r * Math.sin(toRad(start)) };
    const e = { x: cx + r * Math.cos(toRad(end)), y: cy + r * Math.sin(toRad(end)) };
    const large = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  return (
    <svg width={140} height={100} viewBox="0 0 140 100">
      {/* Background arc */}
      <path d={arcPath(startDeg, startDeg + sweepDeg, R)} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" strokeLinecap="round" />
      {/* Value arc */}
      {val > 0 && (
        <path d={arcPath(startDeg, endDeg, R)} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" />
      )}
      {/* Threshold markers */}
      {[64, 30].map((t) => {
        const deg = startDeg + (t / 100) * sweepDeg;
        const inner = R - 8, outer = R + 2;
        return (
          <line key={t}
            x1={cx + inner * Math.cos(toRad(deg))} y1={cy + inner * Math.sin(toRad(deg))}
            x2={cx + outer * Math.cos(toRad(deg))} y2={cy + outer * Math.sin(toRad(deg))}
            stroke="rgba(255,255,255,0.3)" strokeWidth="1.5"
          />
        );
      })}
      {/* Value text */}
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize="22" fontWeight="bold" fill={color} fontFamily="monospace">
        {tsi != null ? Math.round(tsi) : "—"}
      </text>
      <text x={cx} y={cy + 22} textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">TSI %</text>
    </svg>
  );
}

// ── main component ─────────────────────────────────────────────────────────────

interface Props {
  patient: ApiPatient;
  scan: ApiScanDetail | null;
  scanId: number | null;
}

export function ReportView({ patient, scan, scanId }: Props) {
  const [rep, setRep] = useState<ApiRepeatability | null>(null);
  const [repError, setRepError] = useState(false);

  useEffect(() => {
    if (!scanId) return;
    api.repeatability(scanId)
      .then(setRep)
      .catch(() => setRepError(true));
  }, [scanId]);

  if (!scan) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-text-faint text-[13px]">
        <FileText size={28} strokeWidth={1.3} />
        Run a scan first to generate the compliance report.
      </div>
    );
  }

  const tl = trafficLabel(scan.trafficLight);
  const today = new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

  return (
    <div className="p-6">

      {/* Print button (hidden when printing) */}
      <div className="mb-5 flex items-center justify-between print:hidden">
        <div className="flex items-center gap-2">
          <FileText size={15} className="text-accent" strokeWidth={1.7} />
          <span className="font-display text-base font-semibold text-text">Compliance Report</span>
        </div>
        <Button variant="outline" size="sm" onClick={() => window.print()}>
          <Printer size={13} /> Print / Export PDF
        </Button>
      </div>

      {/* ── Report card ── */}
      <div
        id="resoscan-report"
        className="mx-auto max-w-3xl rounded-2xl border border-line bg-bg-card p-0 overflow-hidden"
        style={{ fontFamily: "system-ui, sans-serif" }}
      >

        {/* Header band */}
        <div className="flex items-center justify-between px-7 py-5 border-b border-line"
          style={{ background: "rgba(0,255,170,0.04)" }}>
          <div>
            <div className="font-display text-lg font-bold text-text">ResoScan Clinical Report</div>
            <div className="text-[11px] text-text-muted mt-0.5">
              Resonant Modal Spectroscopy — Bone Fracture Healing Assessment
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-[11px] text-text-faint">Scan #{scan.id}</div>
            <div className="font-mono text-[11px] text-text-faint">{today}</div>
          </div>
        </div>

        {/* Patient + Scan info */}
        <div className="grid grid-cols-2 gap-0 border-b border-line">
          <div className="px-7 py-5 border-r border-line">
            <div className="text-[10px] uppercase tracking-[0.16em] text-text-faint mb-3">Patient</div>
            <div className="font-display text-[16px] font-semibold text-text">{patient.name}</div>
            <div className="text-[12px] text-text-muted mt-1">
              {patient.patientCode} · {patient.age} yr · {patient.sex}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
              <div><span className="text-text-faint">Bone:</span> {patient.bone}</div>
              <div><span className="text-text-faint">Fracture:</span> {patient.fractureType}</div>
              <div><span className="text-text-faint">Smoker:</span> {patient.smoker ? "Yes" : "No"}</div>
              <div><span className="text-text-faint">Diabetic:</span> {patient.diabetic ? "Yes" : "No"}</div>
              {patient.hospital && (
                <div className="col-span-2"><span className="text-text-faint">Hospital:</span> {patient.hospital}</div>
              )}
              {patient.surgeon && (
                <div className="col-span-2"><span className="text-text-faint">Surgeon:</span> {patient.surgeon}</div>
              )}
            </div>
          </div>
          <div className="px-7 py-5">
            <div className="text-[10px] uppercase tracking-[0.16em] text-text-faint mb-3">Scan Details</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
              <div><span className="text-text-faint">Date:</span> {scan.scanDate}</div>
              <div><span className="text-text-faint">Week:</span> {scan.week.toFixed(1)} post-fracture</div>
              <div><span className="text-text-faint">Source:</span>{" "}
                <span className="capitalize">{scan.source}</span>
              </div>
              <div><span className="text-text-faint">f_healthy:</span> {fmt(scan.fHealthyHz, 0, "Hz")}</div>
            </div>
            {scan.source === "sim" && (
              <div className="mt-3 flex items-start gap-1.5 text-[10px] text-text-faint">
                <AlertTriangle size={10} className="mt-0.5 shrink-0" />
                Device unavailable — simulation run through real normalization pipeline
              </div>
            )}
          </div>
        </div>

        {/* TSI + Traffic light */}
        <div className="grid grid-cols-[auto_1fr] gap-0 border-b border-line">
          <div className="px-7 py-5 flex items-center border-r border-line">
            <TsiGauge tsi={scan.tsiPct} trafficLight={scan.trafficLight} />
          </div>
          <div className="px-7 py-5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
              Tibial Stiffness Index
              <span className="print:hidden"><InfoTip k="tsi" side="bottom" /></span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[40px] font-bold leading-none"
                style={{ color: tl.color }}>
                {scan.tsiPct != null ? scan.tsiPct.toFixed(1) : "—"}
              </span>
              <span className="font-mono text-xl text-text-faint">%</span>
            </div>
            <div className="mt-2 text-[11px] text-text-muted">
              Linear form: {fmt(scan.tsiPctLinear, 1)}%
            </div>
            <div className="mt-3 inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-[11px] font-semibold"
              style={{ background: `${tl.color}18`, color: tl.color, border: `1px solid ${tl.color}44` }}>
              <span className="h-2 w-2 rounded-full" style={{ background: tl.color }} />
              {tl.label}
            </div>
          </div>
        </div>

        {/* Resonance findings — REAL measured values from pipeline */}
        <div className="border-b border-line px-7 py-5">
          <div className="flex items-center text-[10px] uppercase tracking-[0.16em] text-text-faint mb-3">
            Resonance Findings <span className="normal-case text-text-faint ml-1">(normalized pipeline output)</span>
            <span className="print:hidden ml-1"><InfoTip k="fPeak" side="bottom" /></span>
          </div>
          <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
            {[
              { label: "f_peak", value: fmt(scan.fPeakHz, 1, "Hz") },
              { label: "f_healthy", value: fmt(scan.fHealthyHz, 0, "Hz") },
              { label: "Damping ζ", value: fmt(scan.zeta, 4) },
              { label: "Q-factor", value: fmt(scan.qFactor, 1) },
              { label: "BW (−3dB)", value: fmt(scan.bandwidthHz, 1, "Hz") },
              { label: "SNR", value: fmt(scan.snrDb, 1, "dB") },
            ].map(({ label, value }) => (
              <div key={label} className="text-center">
                <div className="font-mono text-[16px] font-semibold text-text">{value}</div>
                <div className="text-[10px] text-text-faint mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Normalization proof — the core credibility section */}
        <div className="border-b border-line px-7 py-5">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-3">
            Normalization Proof — Measurement Reliability
            <span className="print:hidden"><InfoTip k="improvement" side="bottom" /></span>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="rounded-lg border border-line p-3 text-center">
              <div className="font-mono text-[22px] font-bold" style={{ color: "var(--danger)" }}>
                ±{fmt(scan.tsiStdRaw, 2)}%
              </div>
              <div className="text-[10px] text-text-faint mt-1">Raw TSI σ (before)</div>
            </div>
            <div className="rounded-lg border border-line p-3 text-center">
              <div className="font-mono text-[22px] font-bold" style={{ color: "var(--safe)" }}>
                ±{fmt(scan.tsiStdNorm, 3)}%
              </div>
              <div className="text-[10px] text-text-faint mt-1">Normalized TSI σ (after)</div>
            </div>
            <div className="rounded-lg border border-line p-3 text-center"
              style={{ background: "rgba(0,255,170,0.06)", borderColor: "rgba(0,255,170,0.2)" }}>
              <div className="font-mono text-[22px] font-bold" style={{ color: "var(--accent)" }}>
                {scan.improvementFactor != null ? `${scan.improvementFactor.toFixed(1)}×` : "—"}
              </div>
              <div className="text-[10px] text-text-faint mt-1">Stability improvement</div>
            </div>
          </div>
          {rep && !repError && (
            <div className="text-[11px] text-text-muted">
              Based on {rep.nSweeps} sweeps · SNR gain: +{fmt(rep.snrGainDb, 1)} dB · CV before: {fmt(rep.tsiCvRaw, 1)}% → after: {fmt(rep.tsiCvNorm, 2)}%
            </div>
          )}
          <div className="mt-2 text-[11px] text-text-faint">
            Pipeline: coherent averaging → linear detrend → Butterworth band-pass (150–1100 Hz) →
            z-score → Welch PSD → parabolic sub-bin interpolation
          </div>
        </div>

        {/* Clinical recommendation */}
        <div className="border-b border-line px-7 py-5">
          <div className="text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
            Clinical Recommendation
          </div>
          <div className="font-display text-[15px] font-semibold text-text mb-2">
            {scan.predictedLabel ?? "—"}
          </div>
          <p className="text-[13px] leading-relaxed text-text-muted">
            {scan.recommendation ?? "—"}
          </p>
          {scan.confidence != null && (
            <div className="mt-2 text-[11px] text-text-faint">
              ML classifier confidence: {scan.confidence.toFixed(1)}%
            </div>
          )}
        </div>

        {/* Methodology + citations */}
        <div className="px-7 py-5">
          <div className="text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
            Methodology &amp; References
          </div>
          <p className="text-[11px] leading-relaxed text-text-muted">
            <strong className="text-text">Resonant Modal Spectroscopy:</strong> A log-frequency chirp
            (50–800 Hz, 1 s) excites the tibial segment via a vibration actuator. The ADXL345 MEMS
            accelerometer captures the impulse response. FFT analysis extracts the resonant frequency
            f<sub>n</sub>. TSI = (f<sub>n</sub>/f<sub>healthy</sub>)² × 100, where f<sub>healthy</sub>
            is the contralateral limb reference.
          </p>
          <div className="mt-3 border-t border-line pt-3 text-[10px] leading-relaxed text-text-faint">
            <strong>References:</strong>{" "}
            Tower, Beals &amp; Duwelius (1993) <em>J Orthop Trauma</em> 7(6):552 — coined TSI via accelerometer+FFT, n=74, p=0.0001 ·
            Mattei et al. (2021) <em>Int Biomechanics</em> 8(1) — Squared Frequency Index ≡ TSI² ·
            Pelker &amp; Saha (1983) — f² ∝ stiffness ·
            Welch (1967) — averaged periodogram (SNR ∝ √N) ·
            Smith &amp; Serra (1987) — parabolic sub-bin interpolation
          </div>
          <div className="mt-3 border-t border-line pt-3 flex items-center justify-between text-[10px] text-text-faint">
            <span>Generated by ResoScan v0.1 · {today}</span>
            <span>This report is for clinical research use only.</span>
          </div>
        </div>

      </div>

      {/* ── Full measurement log (the "everything is real" table) ── */}
      <div className="mx-auto mt-6 max-w-3xl">
        <ScanHistoryTable patientCode={patient.patientCode} highlightScanId={scan.id} />
      </div>

      {/* Print styles */}
      <style jsx global>{`
        @media print {
          body { background: white !important; color: black !important; }
          .print\\:hidden { display: none !important; }
          #resoscan-report {
            border: 1px solid #ccc !important;
            background: white !important;
            color: black !important;
            max-width: 100% !important;
          }
        }
      `}</style>
    </div>
  );
}
