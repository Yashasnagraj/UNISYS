"use client";

import { useMemo } from "react";
import type { Patient } from "@/lib/patients";
import { predict, PRIOR_K, PRIOR_T0, TSI_TARGET } from "@/lib/prediction";

interface Props {
  patient: Patient;
  width?: number;
  height?: number;
  /** thinned single-curve mode (used in patient cards) */
  sparkline?: boolean;
}

function gompertz(t: number, k: number, t0: number): number {
  return 100 * Math.exp(-Math.exp(-k * (t - t0)));
}

export function TrajectoryChart({ patient, width = 760, height = 360, sparkline = false }: Props) {
  const pred = useMemo(() => predict(patient), [patient]);
  const maxWeek = useMemo(() => {
    const last = patient.scans[patient.scans.length - 1].week;
    return Math.max(20, last + 4, (pred.weeksToTarget ?? 0) + 2);
  }, [patient.scans, pred.weeksToTarget]);

  const W = width, H = height;
  const padL = sparkline ? 6 : 36;
  const padR = sparkline ? 6 : 14;
  const padT = sparkline ? 6 : 22;
  const padB = sparkline ? 6 : 32;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const wToX = (w: number) => padL + (w / maxWeek) * innerW;
  const tToY = (tsi: number) => padT + (1 - tsi / 100) * innerH;

  // Build curves
  const N = 120;
  const popPoints: string[] = [];
  const persPoints: string[] = [];
  for (let i = 0; i < N; i++) {
    const w = (i / (N - 1)) * maxWeek;
    popPoints.push(`${i === 0 ? "M" : "L"}${wToX(w).toFixed(2)},${tToY(gompertz(w, PRIOR_K, PRIOR_T0)).toFixed(2)}`);
    persPoints.push(`${i === 0 ? "M" : "L"}${wToX(w).toFixed(2)},${tToY(gompertz(w, pred.fittedK, pred.fittedT0)).toFixed(2)}`);
  }

  const tone =
    pred.daysRemaining === 0
      ? "var(--safe)"
      : pred.daysRemaining === null
        ? "var(--danger)"
        : "var(--caution)";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
      aria-label={`Healing trajectory for ${patient.name}`}>
      <defs>
        <linearGradient id={`pers-fill-${patient.key}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%"  stopColor={tone} stopOpacity="0.25" />
          <stop offset="100%" stopColor={tone} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* horizontal target line (80%) */}
      {!sparkline && (
        <>
          <line x1={padL} x2={W - padR}
            y1={tToY(TSI_TARGET)} y2={tToY(TSI_TARGET)}
            stroke="var(--safe)" strokeOpacity="0.55"
            strokeDasharray="3 4"
          />
          <text x={W - padR} y={tToY(TSI_TARGET) - 6}
            fontFamily="var(--font-mono)" fontSize="10"
            fill="var(--safe)" textAnchor="end">
            safe-to-walk · 80%
          </text>
        </>
      )}

      {/* gridlines */}
      {!sparkline && [25, 50, 75].map((g) => (
        <line key={g}
          x1={padL} x2={W - padR}
          y1={tToY(g)} y2={tToY(g)}
          stroke="var(--line)" strokeOpacity="0.45"
          strokeDasharray="2 4"
        />
      ))}

      {/* population avg (dashed grey) */}
      {!sparkline && (
        <path d={popPoints.join(" ")}
          fill="none" stroke="var(--text-faint)" strokeWidth="1.4"
          strokeDasharray="4 4" opacity="0.7" />
      )}

      {/* personalised area + line */}
      <path
        d={`${persPoints.join(" ")} L${(W - padR).toFixed(2)},${(H - padB).toFixed(2)} L${padL.toFixed(2)},${(H - padB).toFixed(2)} Z`}
        fill={`url(#pers-fill-${patient.key})`}
      />
      <path d={persPoints.join(" ")} fill="none" stroke={tone} strokeWidth={sparkline ? 1.6 : 2.4} />

      {/* scan points */}
      {patient.scans.map((s, i) => {
        const x = wToX(s.week), y = tToY(s.tsiPct);
        return (
          <circle key={i} cx={x} cy={y}
            r={sparkline ? 1.2 : 2.8}
            fill="var(--text)" stroke={tone} strokeWidth={sparkline ? 0.6 : 1.2} />
        );
      })}

      {/* projected clearance marker */}
      {!sparkline && pred.weeksToTarget !== null && pred.daysRemaining !== null && pred.daysRemaining > 0 && (
        <>
          <line
            x1={wToX(pred.weeksToTarget)} x2={wToX(pred.weeksToTarget)}
            y1={padT} y2={H - padB}
            stroke={tone} strokeDasharray="3 4" opacity="0.7"
          />
          <text
            x={wToX(pred.weeksToTarget) + 4}
            y={padT + 12}
            fontFamily="var(--font-mono)" fontSize="10"
            fill={tone}
          >
            projected wk {pred.weeksToTarget.toFixed(1)}
          </text>
        </>
      )}

      {/* current week marker */}
      {!sparkline && (
        <>
          <line
            x1={wToX(pred.currentWeek)} x2={wToX(pred.currentWeek)}
            y1={padT} y2={H - padB}
            stroke="var(--text-faint)" strokeOpacity="0.6"
          />
          <text
            x={wToX(pred.currentWeek) - 4}
            y={padT + 12}
            fontFamily="var(--font-mono)" fontSize="10"
            fill="var(--text-muted)" textAnchor="end"
          >
            today · wk {pred.currentWeek.toFixed(1)}
          </text>
        </>
      )}

      {/* x/y axes */}
      {!sparkline && (
        <>
          <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} stroke="var(--line)" />
          <line x1={padL} x2={padL} y1={padT} y2={H - padB} stroke="var(--line)" />
          {/* x ticks every 4 weeks */}
          {Array.from({ length: Math.ceil(maxWeek / 4) + 1 }).map((_, i) => {
            const w = i * 4;
            return (
              <g key={i}>
                <line x1={wToX(w)} x2={wToX(w)} y1={H - padB} y2={H - padB + 4} stroke="var(--line)" />
                <text x={wToX(w)} y={H - padB + 16} fontFamily="var(--font-mono)" fontSize="10"
                  fill="var(--text-faint)" textAnchor="middle">{w}</text>
              </g>
            );
          })}
          <text x={(padL + W - padR) / 2} y={H - 4} fontFamily="var(--font-mono)" fontSize="10"
            fill="var(--text-faint)" textAnchor="middle">weeks since fracture</text>
          {/* y ticks */}
          {[0, 25, 50, 75, 100].map((g) => (
            <g key={g}>
              <line x1={padL - 4} x2={padL} y1={tToY(g)} y2={tToY(g)} stroke="var(--line)" />
              <text x={padL - 6} y={tToY(g) + 3} fontFamily="var(--font-mono)" fontSize="10"
                fill="var(--text-faint)" textAnchor="end">{g}</text>
            </g>
          ))}
        </>
      )}
    </svg>
  );
}
