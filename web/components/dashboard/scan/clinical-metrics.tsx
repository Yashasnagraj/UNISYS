"use client";

import type { ClinicalMetrics } from "@/lib/scan";

export function ClinicalMetricsGrid({ m }: { m: ClinicalMetrics }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Metric
        label="Tibial Stiffness Index"
        value={m.tsi.toFixed(1)}
        unit="%"
        sub="Bone stiffness vs healthy reference"
        emphasis
      />
      <RustMetric m={m} />
      <Metric
        label="Resonant frequency"
        value={m.fn.toFixed(0)}
        unit="Hz"
        sub="Higher = stiffer bone"
      />
      <Metric
        label="Damping ratio (ζ)"
        value={m.zeta.toFixed(3)}
        sub={
          m.zeta < 0.04 ? "Solid · healed energy retention"
          : m.zeta < 0.10 ? "Stable · still gaining stiffness"
          : "Soft callus · absorbs energy"
        }
      />
      <Metric
        label="Q-Factor"
        value={m.qFactor.toFixed(1)}
        sub={m.qFactor > 14 ? "Sharp · stiff bone" : m.qFactor > 6 ? "Moderate" : "Broad · soft callus"}
      />
      <Metric
        label="Half-power bandwidth"
        value={m.bandwidthHz.toFixed(0)}
        unit="Hz"
        sub="Width of the resonance at half-power"
      />
    </div>
  );
}

function Metric({
  label, value, unit, sub, emphasis = false,
}: { label: string; value: string; unit?: string; sub?: string; emphasis?: boolean; }) {
  return (
    <div className="surface p-5">
      <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">{label}</div>
      <div className={"mt-1 flex items-baseline gap-1 font-mono leading-none " + (emphasis ? "text-text" : "text-text")}>
        <span className={emphasis ? "text-4xl font-semibold" : "text-2xl font-semibold"}>{value}</span>
        {unit && <span className="text-base text-text-faint">{unit}</span>}
      </div>
      {sub && <p className="mt-2 text-[11.5px] leading-snug text-text-muted">{sub}</p>}
    </div>
  );
}

function RustMetric({ m }: { m: ClinicalMetrics }) {
  const cortexColor = (s: number) =>
    s >= 3 ? "var(--safe)" : s >= 2 ? "var(--caution)" : "var(--danger)";

  const labelOf = (n: number) => (n >= 9 ? "Bridging callus" : n >= 6 ? "Early callus" : "No callus");
  return (
    <div className="surface p-5">
      <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
        RUST score (cortex)
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-2xl font-semibold text-text">{m.rust}</span>
        <span className="font-mono text-base text-text-faint">/ 12</span>
        <span className="ml-2 text-[11px] text-text-muted">{labelOf(m.rust)}</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-1.5">
        <CortexCell label="Anterior"  score={m.rustCortex.anterior}  color={cortexColor(m.rustCortex.anterior)} />
        <CortexCell label="Posterior" score={m.rustCortex.posterior} color={cortexColor(m.rustCortex.posterior)} />
        <CortexCell label="Medial"    score={m.rustCortex.medial}    color={cortexColor(m.rustCortex.medial)} />
        <CortexCell label="Lateral"   score={m.rustCortex.lateral}   color={cortexColor(m.rustCortex.lateral)} />
      </div>
    </div>
  );
}

function CortexCell({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <div
      className="flex items-baseline justify-between rounded-md border border-line bg-bg-panel px-2.5 py-1.5"
      style={{ borderColor: `${color}40` }}
    >
      <span className="text-[11px] text-text-muted">{label}</span>
      <span className="font-mono text-[12px] font-semibold" style={{ color }}>
        {score}/3
      </span>
    </div>
  );
}
