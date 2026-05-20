"use client";

import { useMemo } from "react";
import { areaFromPoints, pathFromPoints, type ScanShape } from "@/lib/scan";

interface Props {
  shape: ScanShape;
  /** 0..1 scan progress; controls sweep position + how much of curve is drawn */
  progress: number;
  width?: number;
  height?: number;
  /** if true, render the healthy reference curve as a dashed grey overlay */
  showHealthy?: boolean;
}

export function ResonanceGraph({
  shape, progress, width = 760, height = 320, showHealthy = true,
}: Props) {
  const injuredLine = useMemo(
    () => pathFromPoints(shape.spectrumInjured, width, height, 28, 28),
    [shape.spectrumInjured, width, height]
  );
  const injuredArea = useMemo(
    () => areaFromPoints(shape.spectrumInjured, width, height, 28, 28),
    [shape.spectrumInjured, width, height]
  );
  const healthyLine = useMemo(
    () => pathFromPoints(shape.spectrumHealthy, width, height, 28, 28),
    [shape.spectrumHealthy, width, height]
  );

  const revealW = Math.max(0, Math.min(width, width * progress));
  const peakIdx = shape.spectrumInjured.indexOf(Math.max(...shape.spectrumInjured));
  const peakX = (peakIdx / (shape.spectrumInjured.length - 1)) * width;
  const peakY = 28 + (height - 56) * (1 - shape.spectrumInjured[peakIdx]);
  const peakRevealed = peakX <= revealW;

  // Secondary peak marker for loose implant
  let secondaryX: number | null = null;
  let secondaryY: number | null = null;
  if (shape.secondaryPeakHz) {
    const sx = ((shape.secondaryPeakHz - 20) / (1100 - 20)) * width;
    secondaryX = sx;
    // find nearest spectrum value
    const idx = Math.round((shape.secondaryPeakHz - 20) / (1100 - 20) * (shape.spectrumInjured.length - 1));
    const v = shape.spectrumInjured[Math.max(0, Math.min(shape.spectrumInjured.length - 1, idx))];
    secondaryY = 28 + (height - 56) * (1 - v);
  }

  const ticks = [40, 100, 200, 400, 700, 1000];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img"
      aria-label="Frequency response of the bone" style={{ display: "block" }}>
      <defs>
        <linearGradient id="rg-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%"  stopColor="var(--accent)" stopOpacity="0.45" />
          <stop offset="80%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="rg-sweep" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%"   stopColor="var(--accent)" stopOpacity="0" />
          <stop offset="80%"  stopColor="var(--accent)" stopOpacity="0.05" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.2" />
        </linearGradient>
        <clipPath id="rg-clip">
          <rect x="0" y="0" width={revealW} height={height} />
        </clipPath>
      </defs>

      {/* gridlines */}
      {[0.25, 0.5, 0.75].map((y) => (
        <line key={y}
          x1={0} x2={width}
          y1={28 + (height - 56) * y} y2={28 + (height - 56) * y}
          stroke="var(--line)" strokeOpacity="0.4" strokeDasharray="2 4"
        />
      ))}

      {/* sweep cursor trailing glow */}
      {progress > 0 && progress < 1 && (
        <rect x={Math.max(0, revealW - 160)} y="0" width="160" height={height} fill="url(#rg-sweep)" />
      )}

      {/* healthy reference (always full width, dashed grey) */}
      {showHealthy && (
        <path d={healthyLine} fill="none"
          stroke="var(--text-faint)" strokeOpacity="0.7"
          strokeWidth="1.4" strokeDasharray="4 4"
        />
      )}

      {/* injured curve + fill — clipped to scan progress */}
      <g clipPath="url(#rg-clip)">
        <path d={injuredArea} fill="url(#rg-fill)" />
        <path d={injuredLine} fill="none" stroke="var(--accent)" strokeWidth="2" />
      </g>

      {/* peak marker */}
      {peakRevealed && (
        <g>
          <circle cx={peakX} cy={peakY} r="4" fill="var(--accent)" />
          <circle cx={peakX} cy={peakY} r="10" fill="none" stroke="var(--accent)" strokeOpacity="0.4" />
          <line x1={peakX} x2={peakX} y1={peakY + 12} y2={height - 28}
            stroke="var(--accent)" strokeOpacity="0.35" strokeDasharray="2 3" />
          <text x={peakX} y={peakY - 14} fontFamily="var(--font-mono)" fontSize="11"
            fill="var(--accent)" textAnchor="middle">
            f₀ = {Math.round(shape.peakHz)} Hz
          </text>
        </g>
      )}

      {/* secondary peak (loose implant) */}
      {secondaryX !== null && secondaryY !== null && progress > 0.6 && (
        <g>
          <circle cx={secondaryX} cy={secondaryY} r="3.5" fill="var(--danger)" />
          <circle cx={secondaryX} cy={secondaryY} r="9" fill="none" stroke="var(--danger)" strokeOpacity="0.5" />
          <text x={secondaryX} y={secondaryY - 12} fontFamily="var(--font-mono)" fontSize="10"
            fill="var(--danger)" textAnchor="middle">
            implant rattle
          </text>
        </g>
      )}

      {/* sweep cursor line */}
      {progress > 0 && progress < 1 && (
        <line x1={revealW} x2={revealW} y1="0" y2={height} stroke="var(--accent)" strokeWidth="1" />
      )}

      {/* axes */}
      <line x1="0" x2={width} y1={height - 28} y2={height - 28} stroke="var(--line)" />
      {ticks.map((hz) => {
        const x = ((hz - 20) / (1100 - 20)) * width;
        return (
          <g key={hz}>
            <line x1={x} x2={x} y1={height - 28} y2={height - 22} stroke="var(--line)" />
            <text x={x} y={height - 10} fontFamily="var(--font-mono)" fontSize="10"
              fill="var(--text-faint)" textAnchor="middle">{hz}</text>
          </g>
        );
      })}
      <text x={width - 8} y={20} fontFamily="var(--font-mono)" fontSize="10"
        fill="var(--text-faint)" textAnchor="end">Hz</text>

      {/* legend */}
      {showHealthy && (
        <g transform={`translate(${width - 220}, 36)`}>
          <line x1="0" x2="14" y1="0" y2="0" stroke="var(--accent)" strokeWidth="2" />
          <text x="20" y="3" fontFamily="var(--font-mono)" fontSize="10" fill="var(--text-muted)">
            this patient
          </text>
          <line x1="0" x2="14" y1="14" y2="14" stroke="var(--text-faint)" strokeWidth="1.4" strokeDasharray="3 3" />
          <text x="20" y="17" fontFamily="var(--font-mono)" fontSize="10" fill="var(--text-muted)">
            healthy bone
          </text>
        </g>
      )}
    </svg>
  );
}
