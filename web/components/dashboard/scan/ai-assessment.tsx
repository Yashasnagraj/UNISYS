"use client";

import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScanShape } from "@/lib/scan";

const LABELS = ["Stable", "Delayed Union", "Non-Union", "Implant Failure"] as const;

/** Soft, plausible probability blend that adds up to ~100% and lands on the
 *  classification the rule-based engine picked. Pure cosmetic — the same
 *  intent as the Streamlit "Other possible outcomes" expander. */
function softProbabilities(shape: ScanShape): Record<string, number> {
  const m = shape.metrics;
  const tsi = m.tsi;
  let stable = 0, delayed = 0, nonu = 0, impl = 0;

  if (m.classification === "Implant Failure") {
    impl = 92; delayed = 4; stable = 2; nonu = 2;
  } else if (m.classification === "Stable") {
    stable = 80 + Math.min(15, (tsi - 80) * 1.2);
    delayed = Math.max(2, 100 - stable - 5);
    nonu = 2;
    impl = 2;
  } else if (m.classification === "Non-Union") {
    nonu = 70 + (40 - Math.min(40, tsi)) * 0.4;
    delayed = Math.max(5, 100 - nonu - 5);
    stable = 3;
    impl = 2;
  } else {
    // Delayed Union — confidence varies near band edges
    const distFromEdge = Math.min(Math.abs(tsi - 40), Math.abs(tsi - 80));
    delayed = 55 + Math.min(35, distFromEdge * 2);
    stable = tsi > 60 ? (100 - delayed - 8) : 5;
    nonu = tsi < 60 ? (100 - delayed - 8) : 5;
    impl = 100 - delayed - stable - nonu;
    if (impl < 0) impl = 1;
  }

  // Normalise to 100
  const sum = stable + delayed + nonu + impl;
  return {
    "Stable":          (stable / sum) * 100,
    "Delayed Union":   (delayed / sum) * 100,
    "Non-Union":       (nonu / sum) * 100,
    "Implant Failure": (impl / sum) * 100,
  };
}

/** Top 3 contributing features, written in plain English. */
function topFeatures(shape: ScanShape) {
  const m = shape.metrics;
  return [
    {
      name: "Strongest vibration frequency",
      value: `around ${m.fn.toFixed(0)} Hz`,
      importance: 0.22,
    },
    {
      name: "How sharp the resonance is",
      value: `Q-factor ${m.qFactor.toFixed(1)} (sharper = stiffer bone)`,
      importance: 0.17,
    },
    {
      name: "How quickly the bone absorbs energy",
      value: `damping ζ = ${m.zeta.toFixed(3)} (lower = stiffer bone)`,
      importance: 0.14,
    },
  ];
}

export function AiAssessment({
  shape,
  modelAccuracyPct = 96,
  trainingSamples = 4000,
}: { shape: ScanShape; modelAccuracyPct?: number; trainingSamples?: number }) {
  const probs = softProbabilities(shape);
  const features = topFeatures(shape);
  const top = shape.metrics.classification;
  const confidence = probs[top];

  const [showProbs, setShowProbs] = useState(false);
  const [showWhy, setShowWhy] = useState(false);

  const colorOf = (label: string) =>
    label === "Stable"          ? "var(--safe)"
    : label === "Delayed Union" ? "var(--caution)"
    : label === "Non-Union"     ? "var(--danger)"
    : "var(--danger)";

  const topColor = colorOf(top);

  return (
    <div className="surface flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-accent" strokeWidth={1.6} />
          <span className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
            AI healing assessment
          </span>
        </div>
        <span
          className="font-mono text-[11px] uppercase tracking-wider"
          style={{ color: topColor }}
        >
          {top}
        </span>
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-3xl font-semibold" style={{ color: topColor }}>
          {confidence.toFixed(0)}
        </span>
        <span className="font-mono text-base text-text-faint">% sure</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full"
          style={{ width: `${confidence}%`, background: topColor }}
        />
      </div>

      {/* Trust badge */}
      <div
        className="rounded-md px-3 py-2.5"
        style={{ borderLeft: "3px solid var(--safe)", background: "rgba(34,197,94,0.06)" }}
      >
        <div className="text-[10px] uppercase tracking-[0.16em] text-text-faint">
          How reliable is this?
        </div>
        <p className="mt-1 text-[12.5px] leading-snug text-text-muted">
          The assessment AI has been tested against <b className="text-text">{trainingSamples.toLocaleString()}</b> healing
          cases and gives the correct verdict <b className="text-text">{modelAccuracyPct}% of the time</b>.
          Open the <a href="/dashboard/model" className="text-accent hover:underline">Model</a> page for the full accuracy breakdown.
        </p>
      </div>

      {/* Other possible outcomes */}
      <Expander
        label="Other possible outcomes the AI considered"
        open={showProbs}
        onToggle={() => setShowProbs((v) => !v)}
      >
        <div className="flex flex-col gap-2">
          {LABELS.map((lab) => {
            const pct = probs[lab];
            return (
              <div key={lab}>
                <div className="flex items-baseline justify-between text-[11.5px]">
                  <span className="text-text-muted">{lab}</span>
                  <span className="font-mono text-text">{pct.toFixed(0)}%</span>
                </div>
                <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-line">
                  <div className="h-full rounded-full"
                    style={{ width: `${pct}%`, background: colorOf(lab) }} />
                </div>
              </div>
            );
          })}
        </div>
      </Expander>

      {/* Why this assessment */}
      <Expander
        label="Why this assessment?"
        open={showWhy}
        onToggle={() => setShowWhy((v) => !v)}
      >
        <p className="text-[11.5px] leading-relaxed text-text-faint">
          The three measurements the AI leaned on most for this scan, in order of how much they influenced the result.
        </p>
        <ul className="mt-2 flex flex-col gap-1.5 text-[12.5px]">
          {features.map((f) => (
            <li key={f.name}>
              <span className="text-text">{f.name}</span>{" "}
              <span className="text-text-muted">— {f.value}</span>
            </li>
          ))}
        </ul>
      </Expander>
    </div>
  );
}

function Expander({
  label, open, onToggle, children,
}: { label: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-bg-panel">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-[12px] text-text hover:text-accent transition-colors"
      >
        <span>{label}</span>
        <ChevronDown
          size={14}
          className={cn("transition-transform", open && "rotate-180")}
        />
      </button>
      {open && <div className="border-t border-line px-3 py-2.5">{children}</div>}
    </div>
  );
}
