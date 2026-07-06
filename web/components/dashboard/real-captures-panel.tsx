"use client";

/**
 * Device captures panel — one exhibit per demo patient.
 *
 * Yashas N shows REAL hardware readings ("LIVE HARDWARE"); Priya and Vikram show
 * SIMULATED captures ("DEMO DATA"), clearly labelled. Same layout for all three:
 * the per-press jitter (the cheap-sensor problem), the best clean resonance, and
 * the normalization story.
 *
 * When `scanSignal` changes (a scan was run), the panel shows a 5-second
 * "capturing…" state and then appends a fresh capture row — so pressing Run scan
 * visibly takes a reading and adds it to the log.
 */

import { Fragment, useEffect, useRef, useState } from "react";
import { Radio, Activity, Loader2 } from "lucide-react";
import { getDeviceData, type RealCapture } from "@/lib/real-captures";
import { InfoTip } from "@/components/ui/info-tip";

interface Props {
  patientCode: string;
  /** Increments when a scan is run; triggers a new capture row after ~5 s. */
  scanSignal?: number;
}

const CAPTURE_DELAY_MS = 5000;

/** Generate a believable device reading with natural per-press variation. */
function genCapture(press: number): RealCapture {
  const good = Math.random() > 0.25; // most presses land a clean resonance
  return {
    press,
    fPeakHz: good ? 135 + Math.random() * 28 : 60 + Math.random() * 55,
    qFactor: good ? 42 + Math.random() * 45 : 2 + Math.random() * 18,
    zeta: good ? 0.004 + Math.random() * 0.010 : 0.02 + Math.random() * 0.25,
    snrDb: good ? 13 + Math.random() * 8 : 3 + Math.random() * 7,
  };
}

export function RealCapturesPanel({ patientCode, scanSignal = 0 }: Props) {
  const d = getDeviceData(patientCode);
  const [extra, setExtra] = useState<RealCapture[]>([]);
  const [capturing, setCapturing] = useState(false);
  const lastSignal = useRef(0);

  useEffect(() => {
    if (!d) return;
    // Real hardware exhibit stays frozen to its genuine captured rows — we never
    // fabricate a new "live" reading on a button press. Simulated demo patients
    // (clearly labelled) may append a synthetic row to animate the flow.
    if (d.isReal) return;
    if (scanSignal <= 0 || scanSignal === lastSignal.current) return;
    lastSignal.current = scanSignal;
    setCapturing(true);
    const t = setTimeout(() => {
      setExtra((prev) => [...prev, genCapture(d.captures.length + prev.length + 1)]);
      setCapturing(false);
    }, CAPTURE_DELAY_MS);
    return () => clearTimeout(t);
  }, [scanSignal, d]);

  if (!d) return null;

  const captures = [...d.captures, ...extra];
  const best = captures.reduce((a, b) => (b.qFactor > a.qFactor ? b : a), captures[0]);
  const newestPress = extra.length ? d.captures.length + extra.length : -1;

  const fPeaks = captures.map((c) => c.fPeakHz);
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
        <span className="flex items-center gap-2 font-mono text-[11px] text-text-faint">
          {capturing && (
            <span className="flex items-center gap-1" style={{ color: accent }}>
              <Loader2 size={11} className="animate-spin" /> capturing…
            </span>
          )}
          {d.device}
        </span>
      </div>

      {/* Capture rows */}
      <div className="px-5 py-4">
        <div className="mb-3 grid grid-cols-[auto_1fr_1fr_1fr_1fr] gap-x-4 gap-y-2 text-[12px]">
          <div className="text-[10px] uppercase tracking-wide text-text-faint">Press</div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">f_peak (Hz) <InfoTip k="fPeak" side="bottom" /></div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">Q-factor <InfoTip k="qFactor" side="bottom" /></div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">ζ damping <InfoTip k="zeta" side="bottom" /></div>
          <div className="flex items-center justify-end gap-1 text-[10px] uppercase tracking-wide text-text-faint">SNR (dB) <InfoTip k="snr" side="bottom" /></div>

          {captures.map((c) => {
            const isBest = c.press === best.press;
            const isNew = c.press === newestPress;
            const nameColor = isBest ? accent : "var(--text)";
            return (
              <Fragment key={c.press}>
                <div className="font-mono text-text-muted flex items-center gap-1.5"
                  style={isNew ? { color: accent } : undefined}>
                  {isBest && <Activity size={11} style={{ color: accent }} />}
                  #{c.press}{isNew && <span className="text-[9px] uppercase">new</span>}
                </div>
                <div className="font-mono text-right" style={{ color: nameColor }}>{c.fPeakHz.toFixed(1)}</div>
                <div className="font-mono text-right" style={{ color: isBest ? accent : "var(--text-muted)" }}>{c.qFactor.toFixed(1)}</div>
                <div className="font-mono text-right text-text-muted">{c.zeta.toFixed(4)}</div>
                <div className="font-mono text-right text-text-muted">{c.snrDb.toFixed(1)}</div>
              </Fragment>
            );
          })}

          {/* live "capturing…" placeholder row */}
          {capturing && (
            <>
              <div className="font-mono flex items-center gap-1.5" style={{ color: accent }}>
                <Loader2 size={11} className="animate-spin" /> #{captures.length + 1}
              </div>
              <div className="col-span-4 text-[11px] text-text-faint">
                vibrating bone &amp; reading accelerometer…
              </div>
            </>
          )}
        </div>

        {/* Best capture callout */}
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-line px-3 py-2" style={{ background: tintBg }}>
          <Activity size={14} className="shrink-0" style={{ color: accent }} />
          <div className="text-[12px] text-text-muted">
            <span className="text-text font-semibold">Cleanest capture: {best.fPeakHz.toFixed(1)} Hz</span>
            {" "}— Q={best.qFactor.toFixed(1)}, SNR {best.snrDb.toFixed(1)} dB.
            {best.qFactor >= 50 ? " A high-Q peak means the bone genuinely rang at this frequency."
              : best.qFactor >= 25 ? " A moderate-Q peak — a healing but not-yet-solid bone."
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
