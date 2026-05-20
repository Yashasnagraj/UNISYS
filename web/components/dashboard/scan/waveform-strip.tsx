"use client";

import { useMemo } from "react";
import { pathFromPoints, type ScanShape } from "@/lib/scan";

export function WaveformStrip({
  shape,
  progress,
  width = 760,
  height = 88,
}: { shape: ScanShape; progress: number; width?: number; height?: number; }) {
  const d = useMemo(
    () => pathFromPoints(shape.waveform, width, height, 12, 12),
    [shape.waveform, width, height]
  );
  const revealW = Math.max(0, Math.min(width, width * progress));
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-hidden>
      <defs>
        <clipPath id="wf-clip">
          <rect x="0" y="0" width={revealW} height={height} />
        </clipPath>
      </defs>
      {/* baseline */}
      <line x1="0" x2={width} y1={height / 2} y2={height / 2}
        stroke="var(--line)" strokeOpacity="0.5" strokeDasharray="2 4" />
      <g clipPath="url(#wf-clip)">
        <path d={d} fill="none" stroke="var(--accent)" strokeOpacity="0.85" strokeWidth="1.4" />
      </g>
    </svg>
  );
}
