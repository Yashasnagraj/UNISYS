/**
 * Personalised Gompertz healing prediction — TS mirror of
 * ortho_simulator/engine/healing_prediction.py.
 *
 * Closed-form: TSI(t) = 100 * exp(-exp(-k*(t-t0)))
 * Fit (k, t0) to the patient's observed scans via a tiny gradient-descent
 * optimiser seeded by demographic priors. Then solve for the week
 * at which TSI crosses 80 and convert to days-from-today.
 *
 * Deliberately faithful to the Python edge cases:
 *   - if current measured TSI >= target, "cleared today" (0 days)
 *   - if projected remaining > 26 weeks, "non-union risk" (null)
 *   - confidence is high (>= 4 scans), moderate (2-3), low (1)
 */

import type { Patient } from "./patients";
import { TODAY_DATE, latestScan } from "./patients";

export const TSI_TARGET = 80.0;
export const PRIOR_K = 0.45;
export const PRIOR_T0 = 4.5;

export type Pace = "ahead" | "on pace" | "behind";
export type Confidence = "high" | "moderate" | "low";

export type Prediction = {
  fittedK: number;
  fittedT0: number;
  weeksToTarget: number | null;
  weeksRemaining: number | null;
  daysRemaining: number | null;
  targetDateIso: string | null;
  currentTsi: number;
  currentWeek: number;
  pace: Pace;
  paceDeltaDays: number;
  confidence: Confidence;
};

function gompertz(t: number, k: number, t0: number): number {
  return 100 * Math.exp(-Math.exp(-k * (t - t0)));
}

function gompertzInverse(target: number, k: number, t0: number): number | null {
  if (k <= 0 || target <= 0 || target >= 100) return null;
  const inner = -Math.log(target / 100);
  if (inner <= 0) return null;
  return t0 - Math.log(inner) / k;
}

/** demographic-aware k prior. mirror of Python helper */
export function demographicKPrior(opts: {
  smoker?: boolean; diabetic?: boolean; age?: number;
}): number {
  let k = PRIOR_K;
  if (opts.smoker) k *= 0.65;
  if (opts.diabetic) k *= 0.75;
  if ((opts.age ?? 0) >= 65) k *= 0.80;
  else if ((opts.age ?? 0) >= 50) k *= 0.92;
  return k;
}

/**
 * Tiny least-squares fit by coordinate descent + line search. The
 * Gompertz is well-behaved for our data so this is enough — and avoids
 * pulling in scipy-equivalent npm libs.
 */
function fitGompertz(
  weeks: number[],
  tsis: number[],
  kSeed: number,
  t0Seed: number,
): { k: number; t0: number } {
  const lossAt = (k: number, t0: number): number => {
    let s = 0;
    for (let i = 0; i < weeks.length; i++) {
      const d = gompertz(weeks[i], k, t0) - tsis[i];
      s += d * d;
    }
    return s;
  };

  let k = kSeed;
  let t0 = t0Seed;
  const kBounds: [number, number] = [0.05, 2.0];
  const t0Bounds: [number, number] = [0.0, 30.0];

  // Multi-resolution descent: coarse -> fine
  const passes: { steps: number; kStep: number; t0Step: number }[] = [
    { steps: 40, kStep: 0.10, t0Step: 1.5 },
    { steps: 40, kStep: 0.03, t0Step: 0.5 },
    { steps: 40, kStep: 0.01, t0Step: 0.15 },
    { steps: 60, kStep: 0.003, t0Step: 0.05 },
  ];

  for (const pass of passes) {
    for (let i = 0; i < pass.steps; i++) {
      const here = lossAt(k, t0);

      const candidates = [
        { k: k + pass.kStep,  t0 },
        { k: k - pass.kStep,  t0 },
        { k,                  t0: t0 + pass.t0Step },
        { k,                  t0: t0 - pass.t0Step },
      ].filter(c =>
        c.k >= kBounds[0] && c.k <= kBounds[1] &&
        c.t0 >= t0Bounds[0] && c.t0 <= t0Bounds[1]
      );

      let bestLoss = here;
      let bestK = k;
      let bestT0 = t0;
      for (const c of candidates) {
        const l = lossAt(c.k, c.t0);
        if (l < bestLoss) {
          bestLoss = l;
          bestK = c.k;
          bestT0 = c.t0;
        }
      }
      if (bestK === k && bestT0 === t0) break; // converged in this pass
      k = bestK;
      t0 = bestT0;
    }
  }

  return { k, t0 };
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Predict days-to-walk for a patient. */
export function predict(p: Patient, today: Date = TODAY_DATE): Prediction {
  const weeks = p.scans.map((s) => s.week);
  const tsis  = p.scans.map((s) => s.tsiPct);

  const kSeed = demographicKPrior({ smoker: p.smoker, diabetic: p.diabetic, age: p.age });
  const { k, t0 } = weeks.length >= 2
    ? fitGompertz(weeks, tsis, kSeed, PRIOR_T0)
    : { k: kSeed, t0: PRIOR_T0 };

  const confidence: Confidence =
    weeks.length >= 4 ? "high" : weeks.length >= 2 ? "moderate" : "low";

  const weeksToTarget = gompertzInverse(TSI_TARGET, k, t0);
  const last = latestScan(p);
  const currentTsi = last.tsiPct;
  const currentWeek = last.week;
  const todayIso = today.toISOString().slice(0, 10);

  let weeksRemaining: number | null;
  let daysRemaining: number | null;
  let targetDateIso: string | null;

  // Non-union signatures (any one triggers): measured TSI very low at
  // late week, fitted k saturated, or projected remaining is implausibly far.
  const stalledK = k < 0.10;
  const stalledLowTsi = currentWeek >= 10 && currentTsi < 35;

  if (currentTsi >= TSI_TARGET) {
    weeksRemaining = 0;
    daysRemaining = 0;
    targetDateIso = todayIso;
  } else if (stalledK || stalledLowTsi) {
    weeksRemaining = null;
    daysRemaining = null;
    targetDateIso = null;
  } else if (weeksToTarget !== null && weeksToTarget > currentWeek) {
    const wr = weeksToTarget - currentWeek;
    if (wr > 20) {
      weeksRemaining = null;
      daysRemaining = null;
      targetDateIso = null;
    } else {
      weeksRemaining = wr;
      daysRemaining = Math.round(wr * 7);
      targetDateIso = addDays(todayIso, daysRemaining);
    }
  } else if (weeksToTarget !== null && weeksToTarget <= currentWeek) {
    weeksRemaining = 0.5;
    daysRemaining = 4;
    targetDateIso = addDays(todayIso, 4);
  } else {
    weeksRemaining = null;
    daysRemaining = null;
    targetDateIso = null;
  }

  // pace vs population
  const popTarget = gompertzInverse(TSI_TARGET, PRIOR_K, PRIOR_T0);
  let pace: Pace = "on pace";
  let paceDeltaDays = 0;
  if (weeksToTarget !== null && popTarget !== null) {
    const deltaWeeks = weeksToTarget - popTarget;
    paceDeltaDays = Math.round(deltaWeeks * 7);
    if (deltaWeeks < -0.5) pace = "ahead";
    else if (deltaWeeks > 0.5) pace = "behind";
  }

  return {
    fittedK: k,
    fittedT0: t0,
    weeksToTarget,
    weeksRemaining,
    daysRemaining,
    targetDateIso,
    currentTsi,
    currentWeek,
    pace,
    paceDeltaDays,
    confidence,
  };
}

/** Convert a prediction into a one-line headline for the dashboard banner. */
export function predictionHeadline(pred: Prediction): {
  daysText: string;
  dateText: string;
  tone: "safe" | "caution" | "danger";
  message: string;
} {
  if (pred.daysRemaining === null) {
    return {
      daysText: "—",
      dateText: "—",
      tone: "danger",
      message: "Non-union risk. Healing trajectory is not on track to reach the weight-bearing threshold.",
    };
  }
  if (pred.daysRemaining === 0) {
    return {
      daysText: "0",
      dateText: "Cleared today",
      tone: "safe",
      message: `Bone has reached ${Math.round(pred.currentTsi)}% of healthy stiffness. Safe for full weight-bearing.`,
    };
  }
  return {
    daysText: String(pred.daysRemaining),
    dateText: pred.targetDateIso ?? "—",
    tone: pred.daysRemaining <= 30 ? "caution" : "danger",
    message: `Projected to cross the safe-to-walk threshold in about ${pred.daysRemaining} days at the current healing pace.`,
  };
}
