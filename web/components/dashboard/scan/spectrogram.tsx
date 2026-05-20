"use client";

import { useMemo } from "react";
import type { Spectrogram as SpectrogramData } from "@/lib/scan";

/** Colormap: navy -> cyan -> white-ish, matching brand */
function colorForValue(v: number): string {
  const t = Math.max(0, Math.min(1, v));
  if (t < 0.5) {
    const k = t * 2;
    // navy -> cyan
    const r = Math.round(10 + (6 - 10) * k);
    const g = Math.round(14 + (182 - 14) * k);
    const b = Math.round(23 + (212 - 23) * k);
    return `rgb(${r},${g},${b})`;
  }
  const k = (t - 0.5) * 2;
  // cyan -> warm-white
  const r = Math.round(6 + (240 - 6) * k);
  const g = Math.round(182 + (240 - 182) * k);
  const b = Math.round(212 + (210 - 212) * k);
  return `rgb(${r},${g},${b})`;
}

export function Spectrogram({
  data,
  width = 360,
  height = 200,
}: { data: SpectrogramData; width?: number; height?: number; }) {
  const grid = data.data;
  const rows = grid.length;
  const cols = grid[0]?.length ?? 0;

  // build a tiled rect representation
  const tiles = useMemo(() => {
    const cellW = width / cols;
    const cellH = (height - 28) / rows;  // leave room for axis
    const out: React.ReactNode[] = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const v = grid[r][c];
        if (v < 0.06) continue; // skip near-zero cells to save dom nodes
        const opacity = +Math.min(1, 0.4 + 0.8 * v).toFixed(3);
        out.push(
          <rect key={`${r}-${c}`}
            x={+(c * cellW).toFixed(2)}
            y={+(r * cellH).toFixed(2)}
            width={+(cellW + 0.5).toFixed(2)}
            height={+(cellH + 0.5).toFixed(2)}
            fill={colorForValue(v)} opacity={opacity} />
        );
      }
    }
    return out;
  }, [grid, rows, cols, width, height]);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height}
      role="img" aria-label="Spectrogram — frequency over time">
      {tiles}
      {/* time axis */}
      <line x1="0" x2={width} y1={height - 28} y2={height - 28} stroke="var(--line)" />
      {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
        <text key={i} x={t * width} y={height - 12}
          fontFamily="var(--font-mono)" fontSize="9.5" fill="var(--text-faint)" textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"}>
          {(t * data.tSec * 1000).toFixed(0)} ms
        </text>
      ))}
      {/* freq axis label */}
      <text x="6" y="14" fontFamily="var(--font-mono)" fontSize="10" fill="var(--text-faint)">Hz</text>
    </svg>
  );
}
