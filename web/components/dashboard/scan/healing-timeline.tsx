"use client";

import { useMemo } from "react";

/** Gompertz healing — matches engine/healing_model.py */
function gompertzHealing(week: number, rate = 0.45, inflection = 4.5): number {
  return 100 * Math.exp(-Math.exp(-rate * (week - inflection)));
}

export function HealingTimeline({
  currentWeek,
  currentTsi,
  weeks = 17,
  width = 760,
  height = 200,
}: {
  currentWeek: number;
  currentTsi: number;
  weeks?: number;
  width?: number;
  height?: number;
}) {
  const padL = 32, padR = 16, padT = 18, padB = 30;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;

  const ws = useMemo(() => Array.from({ length: weeks }, (_, i) => i), [weeks]);
  const center = useMemo(() => ws.map((w) => gompertzHealing(w)), [ws]);
  const sd = useMemo(() => ws.map((w) => 8 + 4 * Math.sin((Math.PI * w) / 16)), [ws]);
  const upper = center.map((c, i) => Math.min(100, c + sd[i]));
  const lower = center.map((c, i) => Math.max(0, c - sd[i]));

  const wToX = (w: number) => padL + (w / (weeks - 1)) * innerW;
  const tsiToY = (t: number) => padT + (1 - t / 100) * innerH;

  // Band area path
  const bandPath = useMemo(() => {
    const top = upper.map((v, i) => `${i === 0 ? "M" : "L"}${wToX(i)},${tsiToY(v)}`).join(" ");
    const bottom = lower.slice().reverse().map((v, idx) => {
      const i = ws.length - 1 - idx;
      return `L${wToX(i)},${tsiToY(v)}`;
    }).join(" ");
    return `${top} ${bottom} Z`;
  }, [upper, lower]);

  const centerLine = useMemo(() =>
    center.map((v, i) => `${i === 0 ? "M" : "L"}${wToX(i)},${tsiToY(v)}`).join(" "),
    [center]
  );

  // Phase shading bands along x-axis
  const phases = [
    { range: [0, 2],  label: "Inflammatory",  color: "rgba(239,68,68,0.06)" },
    { range: [2, 6],  label: "Soft callus",   color: "rgba(234,179,8,0.06)" },
    { range: [6, 12], label: "Hard callus",   color: "rgba(6,182,212,0.06)" },
    { range: [12,16], label: "Remodeling",    color: "rgba(34,197,94,0.06)" },
  ];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height}
      role="img" aria-label="Expected healing timeline">
      {/* phase shading */}
      {phases.map((p, i) => (
        <g key={i}>
          <rect
            x={wToX(p.range[0])} y={padT}
            width={wToX(p.range[1]) - wToX(p.range[0])} height={innerH}
            fill={p.color}
          />
          <text x={(wToX(p.range[0]) + wToX(p.range[1])) / 2} y={padT + 12}
            fontFamily="var(--font-mono)" fontSize="9.5" fill="var(--text-faint)"
            textAnchor="middle">
            {p.label}
          </text>
        </g>
      ))}

      {/* 80% threshold */}
      <line x1={padL} x2={width - padR} y1={tsiToY(80)} y2={tsiToY(80)}
        stroke="var(--safe)" strokeOpacity="0.5" strokeDasharray="3 3" />
      <text x={width - padR - 4} y={tsiToY(80) - 4}
        fontFamily="var(--font-mono)" fontSize="9.5" fill="var(--safe)" textAnchor="end">
        safe-to-walk · 80%
      </text>

      {/* expected band */}
      <path d={bandPath} fill="var(--accent)" fillOpacity="0.12" />

      {/* expected center curve */}
      <path d={centerLine} fill="none" stroke="var(--accent)" strokeOpacity="0.65" strokeWidth="1.8" strokeDasharray="3 4" />

      {/* current point */}
      <line
        x1={wToX(currentWeek)} x2={wToX(currentWeek)}
        y1={padT} y2={height - padB}
        stroke="var(--text-muted)" strokeOpacity="0.4"
      />
      <circle
        cx={wToX(currentWeek)} cy={tsiToY(currentTsi)}
        r="5" fill="var(--accent)" stroke="white" strokeWidth="1.5"
      />
      <text
        x={wToX(currentWeek) + 8} y={tsiToY(currentTsi) - 8}
        fontFamily="var(--font-mono)" fontSize="10" fill="var(--accent)"
      >
        now · week {currentWeek.toFixed(0)} · {currentTsi.toFixed(0)}%
      </text>

      {/* axes */}
      <line x1={padL} x2={width - padR} y1={height - padB} y2={height - padB} stroke="var(--line)" />
      <line x1={padL} x2={padL} y1={padT} y2={height - padB} stroke="var(--line)" />
      {/* x ticks */}
      {[0, 4, 8, 12, 16].map((w) => (
        <g key={w}>
          <line x1={wToX(w)} x2={wToX(w)} y1={height - padB} y2={height - padB + 4} stroke="var(--line)" />
          <text x={wToX(w)} y={height - padB + 16}
            fontFamily="var(--font-mono)" fontSize="10" fill="var(--text-faint)" textAnchor="middle">
            wk {w}
          </text>
        </g>
      ))}
      {/* y ticks */}
      {[0, 50, 100].map((y) => (
        <g key={y}>
          <line x1={padL - 4} x2={padL} y1={tsiToY(y)} y2={tsiToY(y)} stroke="var(--line)" />
          <text x={padL - 6} y={tsiToY(y) + 3}
            fontFamily="var(--font-mono)" fontSize="10" fill="var(--text-faint)" textAnchor="end">
            {y}%
          </text>
        </g>
      ))}
    </svg>
  );
}
