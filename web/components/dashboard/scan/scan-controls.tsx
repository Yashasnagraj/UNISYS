"use client";

import { cn } from "@/lib/utils";
import type { ScanParams } from "@/lib/scan";

interface Props {
  params: ScanParams;
  onChange: (next: Partial<ScanParams>) => void;
  className?: string;
}

export function ScanControls({ params, onChange, className }: Props) {
  return (
    <div className={cn("surface flex flex-col gap-5 p-5", className)}>
      <div>
        <div className="text-[10px] uppercase tracking-[0.16em] text-text-faint">
          Scan parameters
        </div>
        <div className="mt-0.5 text-[11px] text-text-muted">
          Try the sliders — every change re-runs the scan, the AI, and the projection in real time.
        </div>
      </div>

      <SliderRow
        label="Callus stiffness"
        unit="%"
        value={params.callusPct}
        min={0}
        max={100}
        step={1}
        onChange={(v) => onChange({ callusPct: v })}
        hint="0% = fresh fracture, 100% = fully healed"
      />

      <SliderRow
        label="Contact pressure"
        unit="N"
        value={params.pressureN}
        min={0}
        max={7}
        step={0.1}
        decimals={1}
        onChange={(v) => onChange({ pressureN: v })}
        hint={
          params.pressureN < 2 ? "Pressure too low — signal will be weak"
          : params.pressureN > 5 ? "Pressure too high — risk of soft-tissue artefact"
          : "Optimal range (2–5 N)"
        }
        tone={
          params.pressureN < 2 || params.pressureN > 5 ? "caution" : "ok"
        }
      />

      <SliderRow
        label="Weeks since fracture"
        unit="wk"
        value={params.week}
        min={0}
        max={16}
        step={1}
        onChange={(v) => onChange({ week: v })}
        hint="Use with stiffness to simulate the patient's recovery week"
      />

      <Toggle
        label="Surgical hardware is loose"
        value={params.implantLoose}
        onChange={(v) => onChange({ implantLoose: v })}
        hint="When checked, the AI looks for a second resonance peak"
      />
    </div>
  );
}

function SliderRow({
  label, unit, value, min, max, step, decimals = 0, onChange, hint, tone = "ok",
}: {
  label: string; unit?: string; value: number; min: number; max: number; step: number;
  decimals?: number; onChange: (v: number) => void; hint?: string; tone?: "ok" | "caution";
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label className="text-[11.5px] text-text">{label}</label>
        <span className="font-mono text-[13px] font-semibold text-text">
          {value.toFixed(decimals)}{unit && <span className="text-text-faint"> {unit}</span>}
        </span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-line accent-[var(--accent)]"
        style={{
          background:
            `linear-gradient(to right, var(--accent) 0%, var(--accent) ${
              ((value - min) / (max - min)) * 100
            }%, var(--line) ${((value - min) / (max - min)) * 100}%, var(--line) 100%)`,
        }}
      />
      {hint && (
        <p
          className="mt-1.5 text-[10.5px] leading-snug"
          style={{ color: tone === "caution" ? "var(--caution)" : "var(--text-faint)" }}
        >
          {hint}
        </p>
      )}
    </div>
  );
}

function Toggle({
  label, value, onChange, hint,
}: { label: string; value: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <div>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className="flex w-full items-center justify-between gap-3"
      >
        <span className="text-[11.5px] text-text">{label}</span>
        <span
          className={cn(
            "relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors",
            value ? "bg-accent" : "bg-line"
          )}
        >
          <span
            className={cn(
              "absolute top-[2px] inline-block h-4 w-4 rounded-full bg-bg-card transition-transform",
              value ? "translate-x-[18px]" : "translate-x-[2px]"
            )}
          />
        </span>
      </button>
      {hint && <p className="mt-1.5 text-[10.5px] leading-snug text-text-faint">{hint}</p>}
    </div>
  );
}
