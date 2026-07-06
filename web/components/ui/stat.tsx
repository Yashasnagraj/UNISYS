"use client";

import { cn } from "@/lib/utils";

/** Label + big mono value (+ optional unit / sub / accent color). The house
 *  style for every metric readout. */
export function Stat({
  label, value, unit, sub, color, size = "md", className, right,
}: {
  label: React.ReactNode; value: React.ReactNode; unit?: string;
  sub?: React.ReactNode; color?: string; size?: "sm" | "md" | "lg";
  className?: string; right?: React.ReactNode;
}) {
  const valueSize = size === "lg" ? "text-[34px]" : size === "sm" ? "text-[18px]" : "text-[24px]";
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.16em] text-text-faint">{label}</span>
        {right}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn("font-mono font-semibold leading-none", valueSize)}
          style={color ? { color } : undefined}>
          {value}
        </span>
        {unit && <span className="font-mono text-[13px] text-text-faint">{unit}</span>}
      </div>
      {sub && <span className="text-[11px] leading-snug text-text-muted">{sub}</span>}
    </div>
  );
}
