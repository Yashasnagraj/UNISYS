"use client";

/**
 * Normalization view — lean and honest.
 *
 * Shows only what's required: the resonant frequency the pipeline locked onto,
 * how much steadier the reading became (raw σ → normalized σ), the SNR gain, a
 * real raw→normalized signal overlay, and the actual processing stages that ran
 * (from GET /api/scans/{id}/normalization + /repeatability). No synthetic traces,
 * no toggle theatrics.
 */

import { useEffect, useState } from "react";
import { Waves, Activity } from "lucide-react";

import { Card, SectionHeader } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { Badge } from "@/components/ui/badge";
import { FadeIn, Stagger } from "@/components/ui/motion";
import { InfoTip } from "@/components/ui/info-tip";
import { api, type ApiNormalization, type ApiRepeatability } from "@/lib/api";

interface Props { scanId: number | null; offline?: boolean }

// ── real raw → normalized signal overlay ─────────────────────────────────────

function SignalOverlay({ raw, norm }: { raw: number[]; norm: number[] }) {
  const W = 640, H = 150, P = 10;
  const cW = W - 2 * P, cH = H - 2 * P;
  const n01 = (a: number[]) => {
    const lo = Math.min(...a), hi = Math.max(...a), r = hi - lo || 1;
    return a.map((v) => (v - lo) / r);
  };
  const path = (sig: number[]) => sig.map((v, i) => {
    const x = P + (i / (sig.length - 1)) * cW;
    const y = P + cH * (1 - v);
    return (i ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
  }).join(" ");
  const hasRaw = raw.length > 1, hasNorm = norm.length > 1;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      {hasRaw && <path d={path(n01(raw))} fill="none" stroke="rgba(255,255,255,0.20)" strokeWidth={1} />}
      {hasNorm && <path d={path(n01(norm))} fill="none" stroke="var(--accent)" strokeWidth={2.2} />}
    </svg>
  );
}

export function NormalizationView({ scanId, offline }: Props) {
  const [norm, setNorm] = useState<ApiNormalization | null>(null);
  const [rep, setRep] = useState<ApiRepeatability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (scanId == null || offline) return;
    setLoading(true); setError(null);
    Promise.all([api.normalization(scanId), api.repeatability(scanId)])
      .then(([n, r]) => { setNorm(n); setRep(r); })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [scanId, offline]);

  if (scanId == null)
    return <Empty>Run a scan first to see the normalization analysis.</Empty>;
  if (loading)
    return <Empty pulse>Loading normalization…</Empty>;
  if (error)
    return <div className="flex h-64 items-center justify-center text-[13px]" style={{ color: "var(--danger)" }}>{error}</div>;

  const fPeak = norm?.fPeakHz ?? 0;
  const stdRaw = rep?.tsiStdRaw ?? 0;
  const stdNorm = rep?.tsiStdNorm ?? 0;
  const snrGain = rep?.snrGainDb ?? norm?.snrGainDb ?? 0;
  const tighter = stdNorm > 1e-6 && stdRaw > stdNorm ? stdRaw / stdNorm : null;

  const stages = norm?.stages ?? [];
  const rawSig = stages[0]?.signal ?? [];
  const normSig = stages[stages.length - 1]?.signal ?? [];

  return (
    <FadeIn className="flex flex-col gap-5 p-6">
      <header>
        <div className="flex items-center gap-2">
          <Waves size={16} className="text-accent" strokeWidth={1.8} />
          <h2 className="font-display text-base font-semibold text-text">Normalization</h2>
        </div>
        <p className="mt-0.5 text-[12px] text-text-muted">
          Turning a noisy single-tap signal into one stable, repeatable reading.
        </p>
      </header>

      {/* Key numbers */}
      <Stagger className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <Stat label={<span className="inline-flex items-center gap-1">Resonant frequency <InfoTip k="fPeak" side="bottom" /></span>}
            value={fPeak.toFixed(1)} unit="Hz" color="var(--accent)"
            sub="Peak the pipeline locked onto" />
        </Card>
        <Card>
          <Stat label={<span className="inline-flex items-center gap-1">Tap-to-tap variation <InfoTip k="improvement" side="bottom" /></span>}
            value={`±${stdRaw.toFixed(1)}`} unit="%"
            right={tighter && tighter >= 1.5 ? <Badge tone="accent">{tighter.toFixed(0)}× tighter</Badge> : undefined}
            sub={tighter && tighter >= 1.5
              ? `normalized to ±${stdNorm.toFixed(1)}%`
              : "across repeated single taps — why averaging is needed"} />
        </Card>
        <Card>
          <Stat label={<span className="inline-flex items-center gap-1">SNR gain <InfoTip k="snrGain" side="bottom" /></span>}
            value={`+${snrGain.toFixed(1)}`} unit="dB" color="var(--safe)"
            sub="Coherent averaging (√N rule)" />
        </Card>
      </Stagger>

      {/* Real raw → normalized signal */}
      <Card>
        <SectionHeader icon={Activity} title="Raw sweep → normalized signal"
          subtitle="Actual captured signal, before and after the pipeline"
          right={<div className="flex items-center gap-3 text-[10.5px]">
            <span className="flex items-center gap-1.5 text-text-muted"><span className="inline-block h-0.5 w-4" style={{ background: "rgba(255,255,255,0.35)" }} /> raw</span>
            <span className="flex items-center gap-1.5 text-text-muted"><span className="inline-block h-0.5 w-4" style={{ background: "var(--accent)" }} /> normalized</span>
          </div>} />
        <div className="mt-3">
          {rawSig.length > 1 || normSig.length > 1
            ? <SignalOverlay raw={rawSig} norm={normSig} />
            : <div className="flex h-[150px] items-center justify-center text-[12px] text-text-faint">No signal data</div>}
        </div>
        <p className="mt-2 text-[11.5px] leading-relaxed text-text-faint">
          The grey trace is one raw tap — mains hum, contact force and sensor noise ride on top of the bone response.
          Averaging, detrending, a mains notch and band-pass strip those out, leaving the clean cyan signal the reading is taken from.
        </p>
      </Card>

      {/* Real pipeline stages */}
      {stages.length > 0 && (
        <Card>
          <SectionHeader icon={Waves} title="Processing pipeline"
            subtitle="Every stage is a standard, peer-reviewed step" />
          <div className="mt-3 flex flex-wrap items-stretch gap-1.5">
            {stages.map((s, i) => (
              <div key={s.name} className="flex items-center gap-1.5">
                <div className="rounded-md border border-line bg-bg-panel px-2.5 py-1.5"
                  style={i === 0 ? undefined : { borderColor: "var(--accent-tint)" }}>
                  <div className="text-[11px] font-semibold capitalize"
                    style={{ color: i === 0 ? "var(--text-muted)" : "var(--accent)" }}>
                    {s.name.replace(/_/g, " ")}
                  </div>
                  <div className="text-[9.5px] text-text-faint max-w-[150px] leading-tight">{s.note}</div>
                </div>
                {i < stages.length - 1 && <span className="text-text-faint text-[11px]">→</span>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Citations */}
      <p className="text-[10.5px] leading-relaxed text-text-faint">
        <span className="text-text-muted font-semibold">Methods:</span>{" "}
        coherent averaging &amp; Welch PSD (Welch 1967) · 50 Hz mains comb-notch · Butterworth band-pass ·
        parabolic sub-bin peak (Smith &amp; Serra 1987). TSI precedent: Tower et&nbsp;al. 1993; Mattei et&nbsp;al. 2021.
      </p>
    </FadeIn>
  );
}

function Empty({ children, pulse }: { children: React.ReactNode; pulse?: boolean }) {
  return (
    <div className={"flex h-64 items-center justify-center text-[13px] " + (pulse ? "animate-pulse text-text-muted" : "text-text-faint")}>
      {children}
    </div>
  );
}
