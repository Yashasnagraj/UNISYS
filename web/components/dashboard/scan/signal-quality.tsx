"use client";

import { cn } from "@/lib/utils";

export function SignalQuality({
  progress,
  score,
}: { progress: number; score: number; }) {
  // 5 dots; light up as scan progresses
  const dots = 5;
  const lit = Math.min(dots, Math.round(progress * dots));
  const label =
    progress < 1 ? "Scanning…" :
    score > 0.85 ? "Excellent" :
    score > 0.65 ? "Good" :
    score > 0.4 ? "Acceptable" :
    "Poor";
  const labelColor =
    progress < 1 ? "var(--text-muted)" :
    score > 0.65 ? "var(--safe)" :
    score > 0.4 ? "var(--caution)" :
    "var(--danger)";
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5">
        {Array.from({ length: dots }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-2 w-2 rounded-full transition-colors duration-200",
              i < lit ? "bg-accent" : "bg-line"
            )}
          />
        ))}
      </div>
      <span className="text-[11px] uppercase tracking-wider" style={{ color: labelColor }}>
        Signal · {label}
      </span>
    </div>
  );
}
