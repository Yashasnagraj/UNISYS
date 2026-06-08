"use client";

/**
 * Device captures panel — one exhibit per demo patient.
 *
 * Yashas N shows REAL hardware readings ("LIVE HARDWARE"); Priya and Vikram show
 * SIMULATED captures ("DEMO DATA"), clearly labelled. Same layout for all three:
 * the per-press jitter (the cheap-sensor problem), the best clean resonance, and
 * the normalization story.
 */

import { Fragment } from "react";
import { Radio, Activity } from "lucide-react";
import { getDeviceData } from "@/lib/real-captures";
import { InfoTip } from "@/components/ui/info-tip";

interface Props {
  patientCode: string;
}

export function RealCapturesPanel({ patientCode }: Props) {
  const d = getDeviceData(patientCode);
  if (!d) return null;

  const fPeaks = d.captures.map((c) => c.fPeakHz);
  const lo = Math.min(...fPeaks);
  const hi = Math.max(...fPeaks);
  const spreadPct = Math.round(((hi - lo) / ((hi + lo) / 2)) * 100);

  const accent = d.isReal ? "var(--accent)" : "var(--caution)";
  const tintBg = d.isReal ? "rgba(0,255,170,0.05)" : "rgba(255,180,50,0.05)";
  const tagBg = d.isReal ? "rgba(0,255,170,0.15)" : "rgba(255,180,50,0.15)";
  const borderTint = d.isReal ? "rgba(0,255,170,0.25)" : "rgba(255,180,50,0.22)";

  return (
    <div className="surface overflow-hidden" style={{ borderColor: borderTint }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line px-5 py-3" style={{ background: tintBg }}>
        <div className="flex items-center gap-2">
          <Radio size={14} strokeWidth={1.8} style={{ color: accent }} />
          <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em]" style={{ color: accent }}>
            {d.isReal ? "Real Device Captures" : "Simulated Captures"}
            <InfoTip k="source" side="bottom" />
          </span>
          <span className="rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
            style={{ background: tagBg, color: accent }}>
            {d.isReal ? "live hardware" : "demo data"}
          </span>
        </div>
        <span className="font-mono text-[11px] text-text-faint">{d.device}</span>
      </div>

      {/* Capture rows */}
      <div className="px-5 py-4">
        <div className="mb-3 grid grid-cols-[auto_1fr_1fr_1fr_1fr] gap-x-4 gap-y-2 text-[12px]">
          <div className="text-[10px] uppercase tracking-wide text-text-faint">Press</div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">f_peak (Hz) <InfoTip k="fPeak" side="bottom" /></div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">Q-factor <InfoTip k="qFactor" side="bottom" /></div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">ζ damping <InfoTip k="zeta" side="bottom" /></div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">SNR (dB) <InfoTip k="snr" side="bottom" /></div>

          {d.captures.map((c) => {
            const isBest = c.press === d.best.press;
            return (
              <Fragment key={c.press}>
                <div className="font-mono text-text-muted flex items-center gap-1.5">
                  {isBest && <Activity size={11} style={{ color: accent }} />}
                  #{c.press}
                </div>
                <div className="font-mono text-right" style={{ color: isBest ? accent : "var(--text)" }}>
                  {c.fPeakHz.toFixed(1)}
                </div>
                <div className="font-mono text-right" style={{ color: isBest ? accent : "var(--text-muted)" }}>
                  {c.qFactor.toFixed(1)}
                </div>
                <div className="font-mono text-right text-text-muted">{c.zeta.toFixed(4)}</div>
                <div className="font-mono text-right text-text-muted">{c.snrDb.toFixed(1)}</div>
              </Fragment>
            );
          })}
        </div>

        {/* Best capture callout */}
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-line px-3 py-2" style={{ background: tintBg }}>
          <Activity size={14} className="shrink-0" style={{ color: accent }} />
          <div className="text-[12px] text-text-muted">
            <span className="text-text font-semibold">Cleanest capture: {d.best.fPeakHz.toFixed(1)} Hz</span>
            {" "}— Q={d.best.qFactor.toFixed(1)}, SNR {d.best.snrDb.toFixed(1)} dB.
            {d.best.qFactor >= 50 ? " A high-Q peak means the bone genuinely rang at this frequency."
              : d.best.qFactor >= 25 ? " A moderate-Q peak — a healing but not-yet-solid bone."
              : " A low-Q, dull peak — the signature of a soft, unbridged fracture."}
          </div>
        </div>

        {/* Jitter → normalization story */}
        <div className="flex items-start gap-2 text-[11px] leading-relaxed text-text-faint">
          <span className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold"
            style={{ background: "rgba(255,180,50,0.12)", color: "var(--caution)" }}>
            ±{spreadPct}% raw spread
          </span>
          <span>{d.note}</span>
        </div>

        {/* Hardware note */}
        <div className="mt-3 border-t border-line pt-2 text-[10px] text-text-faint">
          {d.fsHz} Hz (Nyquist {d.nyquistHz} Hz) · {d.samplesPerChirp} samples/chirp ·
          {d.isReal
            ? " unedited pipeline output. A higher ODR + contralateral baseline would place these in the published 250–450 Hz tibia band."
            : " simulated for this demo patient — runs through the identical normalization pipeline as live hardware."}
        </div>
      </div>
    </div>
  );
}
