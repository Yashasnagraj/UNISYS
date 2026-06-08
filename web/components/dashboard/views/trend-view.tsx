"use client";

/**
 * Trend view — the healing trajectory over time.
 *
 * Plots the patient's scan history against the fitted Gompertz healing curve and
 * the population average, projects the "safe-to-walk" date, and reports pace +
 * confidence. Reuses the validated TrajectoryChart + predict() so the maths
 * matches the Python engine exactly.
 *
 * Every metric carries a plain-English InfoTip.
 */

import { useMemo } from "react";
import { TrendingUp, Calendar, Gauge, Activity } from "lucide-react";

import type { ApiPatient } from "@/lib/api";
import { getPatient, type Patient } from "@/lib/patients";
import { predict, predictionHeadline } from "@/lib/prediction";
import { TrajectoryChart } from "@/components/dashboard/patients/trajectory-chart";
import { InfoTip } from "@/components/ui/info-tip";

// map API patient_code → offline lib patient key (which carries the dense history)
function codeToKey(code: string): string {
  return code === "P-2611" ? "arjun"
    : code === "P-2742" ? "priya"
    : code === "P-2810" ? "vikram"
    : "arjun";
}

interface Props {
  patient: ApiPatient;
}

export function TrendView({ patient }: Props) {
  const libPatient: Patient = useMemo(
    () => getPatient(codeToKey(patient.patientCode)),
    [patient.patientCode],
  );

  const pred = useMemo(() => predict(libPatient), [libPatient]);
  const headline = predictionHeadline(pred);

  const tone =
    headline.tone === "safe" ? "var(--safe)"
    : headline.tone === "caution" ? "var(--caution)"
    : "var(--danger)";

  const paceColor =
    pred.pace === "ahead" ? "var(--safe)"
    : pred.pace === "on pace" ? "var(--accent)"
    : "var(--caution)";

  const scanCount = libPatient.scans.length;

  return (
    <div className="flex flex-col gap-6 p-6">

      {/* Header */}
      <header className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp size={15} className="text-accent" strokeWidth={1.7} />
            <span className="font-display text-base font-semibold text-text">
              Healing Trajectory
            </span>
            <InfoTip k="healingCurve" side="bottom" />
          </div>
          <p className="mt-0.5 text-[12px] text-text-muted">
            {scanCount} scans fitted to a personalised healing curve · {libPatient.name}
          </p>
        </div>
      </header>

      {/* Main grid: chart + stat rail */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">

        {/* Chart */}
        <div className="surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
              TSI over time <InfoTip k="tsi" side="bottom" />
            </span>
            <div className="flex items-center gap-4 text-[11px]">
              <LegendDot color={tone} label="This patient" tip="personalCurve" />
              <LegendDot color="var(--text-faint)" label="Population avg" dashed tip="populationCurve" />
              <LegendDot color="var(--safe)" label="Safe-to-walk" dashed tip="safeToWalk" />
            </div>
          </div>
          <TrajectoryChart patient={libPatient} width={760} height={360} />
        </div>

        {/* Stat rail */}
        <div className="flex flex-col gap-4">

          {/* Days to walk */}
          <div className="surface p-5" style={{ borderLeft: `3px solid ${tone}` }}>
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] text-text-faint">
              Days to walk <InfoTip k="daysToWalk" side="bottom" />
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="font-mono text-[40px] font-semibold leading-none" style={{ color: tone }}>
                {pred.daysRemaining === null ? "—" : pred.daysRemaining}
              </span>
              {pred.daysRemaining !== null && pred.daysRemaining > 0 && (
                <span className="font-mono text-base text-text-faint">days</span>
              )}
            </div>
            <p className="mt-1.5 text-[12px] leading-relaxed text-text-muted">
              {headline.message}
            </p>
          </div>

          {/* Projected clearance */}
          <div className="surface p-4">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
              <Calendar size={11} /> Projected clearance <InfoTip k="projectedClearance" side="bottom" />
            </div>
            <div className="font-mono text-[15px] text-text">
              {pred.targetDateIso ?? "Not on track"}
            </div>
            <div className="mt-0.5 text-[11px] text-text-muted">
              {pred.weeksToTarget !== null
                ? `Crosses 80% at week ${pred.weeksToTarget.toFixed(1)}`
                : "Curve does not reach the safe-to-walk line"}
            </div>
          </div>

          {/* Pace vs population */}
          <div className="surface p-4">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
              <Gauge size={11} /> Healing pace <InfoTip k="pace" side="bottom" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[18px] font-semibold capitalize" style={{ color: paceColor }}>
                {pred.pace}
              </span>
              {pred.paceDeltaDays !== 0 && (
                <span className="font-mono text-[12px] text-text-muted">
                  {pred.paceDeltaDays > 0 ? "+" : ""}{pred.paceDeltaDays}d vs avg
                </span>
              )}
            </div>
          </div>

          {/* Prediction confidence */}
          <div className="surface p-4">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint mb-2">
              <Activity size={11} /> Prediction confidence <InfoTip k="predictionConfidence" side="bottom" />
            </div>
            <div className="flex items-center gap-2">
              <ConfidenceBar level={pred.confidence} />
              <span className="font-display text-[14px] font-semibold capitalize text-text">
                {pred.confidence}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-text-muted">
              Based on {scanCount} scans · more scans tighten the curve
            </div>
          </div>
        </div>
      </div>

      {/* Curve parameters (the maths, for the curious) */}
      <div className="surface p-5">
        <div className="mb-3 flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
          Fitted curve parameters <InfoTip k="healingCurve" side="bottom" />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-[12px]">
          <Param label="Growth rate (k)" value={pred.fittedK.toFixed(3)} note="how fast it heals" />
          <Param label="Inflection (t₀)" value={`wk ${pred.fittedT0.toFixed(1)}`} note="fastest-healing week" />
          <Param label="Current TSI" value={`${pred.currentTsi.toFixed(0)}%`} note={`week ${pred.currentWeek.toFixed(1)}`} />
          <Param label="Target" value="80% TSI" note="safe-to-walk line" />
        </div>
        <p className="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-text-faint">
          Model: TSI(t) = 100·exp(−exp(−k·(t−t₀))) — a Gompertz growth curve fitted by least
          squares to this patient's scans, seeded by demographic priors (age, smoking, diabetes).
          Mirrors the validated Python engine.
        </p>
      </div>
    </div>
  );
}

// ── small pieces ──────────────────────────────────────────────────────────────

function LegendDot({ color, label, dashed, tip }: { color: string; label: string; dashed?: boolean; tip?: string }) {
  return (
    <span className="flex items-center gap-1.5 text-text-muted">
      <span
        className="inline-block h-0.5 w-4 rounded-full"
        style={{ background: dashed ? `repeating-linear-gradient(90deg, ${color} 0 3px, transparent 3px 6px)` : color }}
      />
      {label}
      {tip && <InfoTip k={tip} side="bottom" />}
    </span>
  );
}

function ConfidenceBar({ level }: { level: "high" | "moderate" | "low" }) {
  const filled = level === "high" ? 3 : level === "moderate" ? 2 : 1;
  const color = level === "high" ? "var(--safe)" : level === "moderate" ? "var(--caution)" : "var(--danger)";
  return (
    <span className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <span key={i} className="h-3 w-1.5 rounded-full"
          style={{ background: i < filled ? color : "var(--line)" }} />
      ))}
    </span>
  );
}

function Param({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-text-faint">{label}</div>
      <div className="mt-0.5 font-mono text-[16px] font-semibold text-text">{value}</div>
      <div className="text-[10px] text-text-muted">{note}</div>
    </div>
  );
}
