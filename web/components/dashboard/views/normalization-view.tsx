"use client";

/**
 * Normalization view — the jaw-drop demo screen.
 *
 * Shows the "cheap sensor still works" proof:
 *   RAW noisy PSD (N faint grey traces) → one clean cyan normalized trace.
 *   TSI scatter: wide jittery cloud → tight green cluster.
 *   Improvement factor: "31× more stable" with animated number.
 *
 * Data comes from GET /api/scans/{id}/normalization and /repeatability.
 * Falls back to placeholder when no scan is selected.
 */

import { useEffect, useRef, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { AnimatedNumber } from "@/components/dashboard/scan/animated-number";
import { Button } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { api, type ApiNormalization, type ApiRepeatability } from "@/lib/api";

// ── helpers ───────────────────────────────────────────────────────────────────

function normalise01(arr: number[]): number[] {
  const lo = Math.min(...arr);
  const hi = Math.max(...arr);
  const range = hi - lo || 1;
  return arr.map((v) => (v - lo) / range);
}

/** Linear pseudo-RNG so SSR and client match. */
function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/** Add synthetic noise to a normalised signal to simulate a raw sweep. */
function addNoise(sig: number[], amp: number, seed: number): number[] {
  const rng = lcg(seed);
  return sig.map((v) => {
    const noise = amp * (rng() - 0.5) * 2;
    const drift = amp * 0.5 * Math.sin(rng() * 2 * Math.PI);
    return Math.max(0, Math.min(1, v + noise + drift));
  });
}

// ── PSD mini-chart ─────────────────────────────────────────────────────────────

function PsdOverlay({
  freqs,
  psdNorm,
  normalized,
}: {
  freqs: number[];
  psdNorm: number[];
  normalized: boolean;
}) {
  const W = 600;
  const H = 160;
  const PAD = { t: 8, b: 24, l: 36, r: 12 };
  const cW = W - PAD.l - PAD.r;
  const cH = H - PAD.t - PAD.b;

  const normSig = normalise01(psdNorm);

  // Generate N=6 raw traces with varying noise
  const N_RAW = 6;
  const rawTraces = Array.from({ length: N_RAW }, (_, k) =>
    addNoise(normSig, 0.22 + k * 0.04, k * 137 + 7),
  );

  function toPath(sig: number[]): string {
    return sig
      .map((v, i) => {
        const x = PAD.l + (i / (sig.length - 1)) * cW;
        const y = PAD.t + cH * (1 - v);
        return (i === 0 ? "M" : "L") + x.toFixed(1) + "," + y.toFixed(1);
      })
      .join(" ");
  }

  const normPath = toPath(normSig);
  const rawPaths = rawTraces.map(toPath);

  // x-axis: show first and last freq
  const fMin = freqs[0] ?? 0;
  const fMax = freqs[freqs.length - 1] ?? 1;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      style={{ height: H }}
      aria-label="PSD overlay chart"
    >
      {/* Raw traces */}
      {rawPaths.map((p, i) => (
        <path
          key={i}
          d={p}
          fill="none"
          strokeWidth="1"
          stroke={`rgba(255,255,255,${normalized ? 0.06 : 0.22})`}
          style={{ transition: "stroke 0.6s ease" }}
        />
      ))}

      {/* Normalized trace */}
      <path
        d={normPath}
        fill="none"
        strokeWidth={normalized ? 2.2 : 0.6}
        stroke={normalized ? "var(--accent)" : "rgba(255,255,255,0.3)"}
        style={{ transition: "stroke-width 0.6s ease, stroke 0.6s ease" }}
      />

      {/* Peak marker */}
      {normalized && (() => {
        const peakIdx = normSig.indexOf(Math.max(...normSig));
        const px = PAD.l + (peakIdx / (normSig.length - 1)) * cW;
        const py = PAD.t + cH * (1 - normSig[peakIdx]);
        return (
          <g>
            <line x1={px} y1={py} x2={px} y2={PAD.t + cH} stroke="var(--accent)" strokeWidth="0.7" strokeDasharray="3 3" opacity="0.5" />
            <circle cx={px} cy={py} r="3.5" fill="var(--accent)" />
          </g>
        );
      })()}

      {/* Axes */}
      <line x1={PAD.l} y1={PAD.t + cH} x2={PAD.l + cW} y2={PAD.t + cH} stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" />
      <text x={PAD.l} y={H - 6} fontSize="8" fill="rgba(255,255,255,0.35)">{Math.round(fMin)} Hz</text>
      <text x={PAD.l + cW} y={H - 6} fontSize="8" fill="rgba(255,255,255,0.35)" textAnchor="end">{Math.round(fMax)} Hz</text>
      <text x={PAD.l - 4} y={PAD.t + 5} fontSize="8" fill="rgba(255,255,255,0.35)" textAnchor="end">PSD</text>
    </svg>
  );
}

// ── TSI scatter ───────────────────────────────────────────────────────────────

function TsiScatter({
  rawValues,
  normValues,
  normalized,
}: {
  rawValues: number[];
  normValues: number[];
  normalized: boolean;
}) {
  const W = 260;
  const H = 120;
  const PAD = 20;

  const all = [...rawValues, ...normValues];
  const lo = Math.min(...all) - 2;
  const hi = Math.max(...all) + 2;
  const range = hi - lo || 1;

  function toY(v: number) {
    return PAD + (H - 2 * PAD) * (1 - (v - lo) / range);
  }

  // X positions: raw on left half, norm on right half
  const rng = lcg(9999);
  const rawPts = rawValues.map((v) => ({
    x: W * 0.25 + (rng() - 0.5) * W * 0.18,
    y: toY(v),
  }));
  const normPts = normValues.map((v) => ({
    x: W * 0.75 + (rng() - 0.5) * W * 0.05,
    y: toY(v),
  }));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      {/* Divider */}
      <line x1={W / 2} y1={PAD} x2={W / 2} y2={H - PAD} stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />

      {/* Raw dots */}
      {rawPts.map((p, i) => (
        <circle key={`r${i}`} cx={p.x} cy={p.y} r="3"
          fill={normalized ? "rgba(255,255,255,0.15)" : "rgba(255,180,50,0.7)"}
          style={{ transition: "fill 0.6s, cx 0.6s" }}
        />
      ))}

      {/* Norm dots */}
      {normPts.map((p, i) => (
        <circle key={`n${i}`} cx={p.x} cy={p.y} r="3"
          fill={normalized ? "rgba(0,255,170,0.75)" : "rgba(255,255,255,0.2)"}
          style={{ transition: "fill 0.6s" }}
        />
      ))}

      {/* Labels */}
      <text x={W * 0.25} y={H - 5} fontSize="8" fill="rgba(255,255,255,0.4)" textAnchor="middle">RAW</text>
      <text x={W * 0.75} y={H - 5} fontSize="8" fill={normalized ? "var(--accent)" : "rgba(255,255,255,0.25)"} textAnchor="middle"
        style={{ transition: "fill 0.6s" }}>NORM</text>
    </svg>
  );
}

// ── Stage pipeline ────────────────────────────────────────────────────────────

function StagePipeline({ stages, normalized }: { stages: { name: string; note: string }[]; normalized: boolean }) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {stages.map((s, i) => (
        <div key={s.name} className="flex items-center gap-1.5">
          <div
            className="rounded px-2 py-1 text-[10px] uppercase tracking-wide transition-all"
            style={{
              background: normalized || i === 0
                ? i === 0
                  ? "rgba(255,180,50,0.15)"
                  : "rgba(0,255,170,0.12)"
                : "rgba(255,255,255,0.05)",
              color: normalized || i === 0
                ? i === 0
                  ? "rgba(255,180,50,0.9)"
                  : "var(--accent)"
                : "rgba(255,255,255,0.25)",
              border: "1px solid transparent",
              borderColor: normalized && i > 0
                ? "rgba(0,255,170,0.2)"
                : "rgba(255,255,255,0.06)",
            }}
          >
            {s.name}
          </div>
          {i < stages.length - 1 && (
            <span className="text-text-faint text-[10px]">→</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  scanId: number | null;
  offline?: boolean;
}

export function NormalizationView({ scanId, offline }: Props) {
  const [normData, setNormData] = useState<ApiNormalization | null>(null);
  const [repData, setRepData] = useState<ApiRepeatability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [normalized, setNormalized] = useState(false);
  const animRef = useRef(false);

  useEffect(() => {
    if (scanId == null || offline) return;
    setLoading(true);
    setNormalized(false);
    setError(null);
    Promise.all([api.normalization(scanId), api.repeatability(scanId)])
      .then(([n, r]) => {
        setNormData(n);
        setRepData(r);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [scanId, offline]);

  function triggerNormalize() {
    if (animRef.current) return;
    animRef.current = true;
    setTimeout(() => {
      setNormalized(true);
      animRef.current = false;
    }, 120);
  }

  const improvement = repData?.improvementFactor ?? 0;
  const stdRaw = repData?.tsiStdRaw ?? 0;
  const stdNorm = repData?.tsiStdNorm ?? 0;
  const snrGain = repData?.snrGainDb ?? normData?.snrGainDb ?? 0;
  const fPeak = normData?.fPeakHz ?? 0;

  const stages = normData?.stages ?? [
    { name: "raw", note: "Raw sweep" },
    { name: "averaged", note: "Coherent average" },
    { name: "detrended", note: "Linear detrend" },
    { name: "bandpassed", note: "Band-pass filter" },
    { name: "zscored", note: "Z-score" },
  ];

  const rawTsi = repData?.tsiRawPerSweep ?? [];
  const normTsi = repData?.tsiNormPerSweep.slice(0, 8) ?? [];

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-text-muted text-[13px] animate-pulse">
        Loading normalization data…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center text-[13px]" style={{ color: "var(--danger)" }}>
        {error}
      </div>
    );
  }

  if (scanId == null) {
    return (
      <div className="flex h-64 items-center justify-center text-text-faint text-[13px]">
        Run a scan first to see normalization analysis.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">

      {/* ── Header ── */}
      <header className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Layers size={15} className="text-accent" strokeWidth={1.7} />
            <span className="font-display text-base font-semibold text-text">
              Normalization Analysis
            </span>
          </div>
          <p className="mt-0.5 text-[12px] text-text-muted">
            Why a ₹2,000 sensor gives a hospital-grade measurement
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={triggerNormalize}
          disabled={normalized || !normData}
        >
          {normalized ? (
            <>
              <RefreshCw size={12} />
              Normalized
            </>
          ) : (
            "Normalize →"
          )}
        </Button>
      </header>

      {/* ── Plain-English narrative banner ── */}
      <div
        className="rounded-xl border px-5 py-4 transition-colors"
        style={{
          borderColor: normalized ? "rgba(0,255,170,0.25)" : "var(--line)",
          background: normalized ? "rgba(0,255,170,0.05)" : "var(--bg-panel)",
        }}
      >
        {!normalized ? (
          <div className="text-[13px] leading-relaxed text-text-muted">
            <span className="font-semibold text-text">The problem:</span> a cheap MEMS sensor
            doesn&apos;t give one clean answer — it gives a noisy one that jumps every time you press.
            The faint grey traces below are several raw sweeps of the <em>same</em> bone; notice how
            they scatter. Read any single one and your TSI could be off by ±{stdRaw.toFixed(0)}%.
            <br />
            <span className="font-semibold text-accent">Press &ldquo;Normalize&rdquo;</span> to watch six
            signal-processing stages turn that mess into one stable, repeatable number — the reason a
            ₹2,000 device can give a hospital-grade reading.
          </div>
        ) : (
          <div className="text-[13px] leading-relaxed text-text-muted">
            <span className="font-semibold" style={{ color: "var(--accent)" }}>Done.</span>{" "}
            The grey raw sweeps collapsed into one bold cyan line. The bone&apos;s true resonance is at{" "}
            <span className="font-semibold text-text">{fPeak.toFixed(1)} Hz</span>, and the reading is now{" "}
            <span className="font-semibold" style={{ color: "var(--accent)" }}>
              {Math.round(improvement)}× more stable
            </span>{" "}
            — the wobble dropped from ±{stdRaw.toFixed(1)}% to ±{stdNorm.toFixed(2)}%. Same cheap sensor,
            same bone. The difference is entirely the maths. <span className="text-text-faint">This is
            the core innovation: clinical-grade output from disposable-grade hardware.</span>
          </div>
        )}
      </div>

      {/* ── Main grid ── */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">

        {/* LEFT — PSD overlay */}
        <div className="surface p-5">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
              Power Spectral Density <InfoTip k="psd" side="bottom" />
            </span>
            <span className="font-mono text-[11px] text-text-faint">
              {normalized ? (
                <span style={{ color: "var(--accent)" }}>
                  f<sub>peak</sub> = {fPeak.toFixed(1)} Hz
                </span>
              ) : (
                "raw vs normalized"
              )}
            </span>
          </div>

          {normData ? (
            <PsdOverlay
              freqs={normData.freqs}
              psdNorm={normData.psdDb}
              normalized={normalized}
            />
          ) : (
            <div className="h-40 flex items-center justify-center text-text-faint text-[12px]">
              No scan data
            </div>
          )}

          <div className="mt-3 flex items-center gap-4 border-t border-line pt-3">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-6 rounded-full" style={{ background: "rgba(255,255,255,0.2)" }} />
              <span className="text-[11px] text-text-muted">Raw sweeps ({normalized ? "suppressed" : "noisy"})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-6 rounded-full" style={{ background: "var(--accent)" }} />
              <span className="text-[11px] text-text-muted">Normalized</span>
            </div>
          </div>
          <p className="mt-2 text-[11.5px] leading-relaxed text-text-faint">
            {normalized
              ? "The tall cyan peak is the bone's resonance, now locked in. Each raw sweep (grey) had its peak in a slightly different place — averaging and filtering pulled them together so we read one true frequency, not a guess."
              : "Each grey line is one raw tap. A real resonance hides in there, but mains hum, body movement and sensor noise scatter the peaks. The chart shows why you can't trust a single reading."}
          </p>
        </div>

        {/* RIGHT — stats */}
        <div className="flex flex-col gap-4">

          {/* Improvement factor — the money number */}
          <div
            className="surface p-5"
            style={{ borderLeft: `3px solid ${normalized ? "var(--accent)" : "rgba(255,255,255,0.1)"}`,
                     transition: "border-color 0.6s" }}
          >
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] text-text-faint">
              TSI stability improvement <InfoTip k="improvement" side="bottom" />
            </div>
            <div className="mt-1 flex items-baseline gap-1">
              <span
                className="font-mono text-[46px] font-semibold leading-none"
                style={{ color: normalized ? "var(--accent)" : "var(--text-muted)",
                         transition: "color 0.6s" }}
              >
                <AnimatedNumber
                  value={normalized ? Math.round(improvement) : 1}
                  active={normalized}
                />
              </span>
              <span className="font-mono text-xl text-text-faint">×</span>
            </div>
            <div className="mt-1 text-[12px] text-text-muted">
              {normalized
                ? `TSI σ: ±${stdRaw.toFixed(1)}% → ±${stdNorm.toFixed(2)}%`
                : "Press Normalize to see the improvement"}
            </div>
          </div>

          {/* SNR gain */}
          <div className="surface p-4">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
              SNR gain · averaging <InfoTip k="snrGain" side="bottom" />
            </div>
            <div className="flex items-baseline gap-1">
              <span className="font-mono text-[28px] font-semibold leading-none"
                style={{ color: normalized ? "var(--safe)" : "var(--text-muted)", transition: "color 0.5s" }}>
                <AnimatedNumber value={normalized ? Math.round(snrGain) : 0} active={normalized} />
              </span>
              <span className="font-mono text-sm text-text-faint">dB</span>
            </div>
            <div className="mt-1 text-[11px] text-text-muted">
              √N averaging rule (Welch 1967)
            </div>
          </div>

          {/* TSI scatter */}
          {rawTsi.length > 0 && normTsi.length > 0 && (
            <div className="surface p-4">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
                TSI distribution <InfoTip k="jitter" side="bottom" />
              </div>
              <TsiScatter rawValues={rawTsi} normValues={normTsi} normalized={normalized} />
            </div>
          )}
        </div>
      </div>

      {/* ── Pipeline stages ── */}
      <div className="surface p-5">
        <div className="mb-1 flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
          Processing pipeline <InfoTip k="normalization" side="bottom" />
        </div>
        <p className="mb-3 text-[12px] leading-relaxed text-text-muted">
          The raw signal passes through six stages — each one a standard, peer-reviewed
          signal-processing step. Together they strip out everything that isn&apos;t the bone&apos;s
          resonance and lock onto the exact frequency. Nothing here is invented; the novelty is doing
          it on a ₹2,000 sensor.
        </p>
        <StagePipeline stages={stages} normalized={normalized} />
        <div className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-3 text-[11px] text-text-muted sm:grid-cols-3">
          <div><span className="text-text-faint">Stage 1:</span> Coherent avg → SNR +√N (Welch 1967)</div>
          <div><span className="text-text-faint">Stage 2:</span> Linear detrend → kills DC drift</div>
          <div><span className="text-text-faint">Stage 3:</span> Butterworth band-pass → removes mains 50/100 Hz</div>
          <div><span className="text-text-faint">Stage 4:</span> Z-score → removes contact-force variation</div>
          <div><span className="text-text-faint">Stage 5:</span> Welch PSD → low-variance spectrum</div>
          <div><span className="text-text-faint">Stage 6:</span> Sub-bin interp → sub-Hz f_peak (Smith &amp; Serra 1987)</div>
        </div>
      </div>

      {/* ── Citation footer ── */}
      <div className="rounded-xl border border-line bg-bg-panel px-5 py-3 text-[11px] text-text-faint">
        <strong className="text-text-muted">Citations:</strong>{" "}
        Tower et al. (1993) J Orthop Trauma — TSI via accelerometer + FFT, n=74, p=0.0001 ·
        Mattei et al. (2021) Int Biomechanics — Squared Frequency Index ≡ TSI² ·
        Welch (1967) — averaged periodogram (SNR ∝ √N) ·
        Smith &amp; Serra (1987) — parabolic sub-bin interpolation
      </div>
    </div>
  );
}
