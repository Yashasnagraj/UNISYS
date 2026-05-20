/**
 * Client-side scan signal + clinical metrics generator.
 *
 * Lorentzian PSD shape from a damped SDOF oscillator at f_n with damping
 * zeta — visually indistinguishable from a real Welch PSD for a single
 * resonance. Adds healthy reference, time-domain waveform, spectrogram, and
 * full clinical metrics (TSI, RUST, Q-factor, MDF, half-power bandwidth).
 */

import type { Patient } from "./patients";
import { latestScan } from "./patients";

// ---------------------------------------------------------------------------
//  Physical model — mirrors engine/signal_generator.py
// ---------------------------------------------------------------------------

export const F_HEALTHY_HZ = 850;
export const SCAN_F_MIN = 20;
export const SCAN_F_MAX = 1100;
export const SCAN_N_FREQS = 240;
export const SCAN_WAVEFORM_SAMPLES = 320;
export const SCAN_DURATION_S = 0.5;

/** callus_pct (0..100) -> resonant frequency (Hz). */
export function callusToFrequency(callusPct: number, fHealthy = F_HEALTHY_HZ): number {
  const c = Math.max(0, Math.min(100, callusPct));
  return 300 + 500 * Math.sqrt(c / 100);
}

/** callus_pct (0..100) -> damping ratio zeta. */
export function callusToDamping(callusPct: number): number {
  const c = Math.max(0, Math.min(100, callusPct));
  return 0.20 - 0.175 * Math.pow(c / 100, 1.3);
}

function lorentzian(f: number, fn: number, zeta: number): number {
  const r = f / fn;
  const denom = Math.sqrt(Math.pow(1 - r * r, 2) + Math.pow(2 * zeta * r, 2));
  return 1 / denom;
}

// ---------------------------------------------------------------------------
//  Parametric scan params (used by sliders)
// ---------------------------------------------------------------------------

export type ScanParams = {
  callusPct: number;       // 0..100
  pressureN: number;       // 0..7  (3.5 = ideal)
  implantLoose: boolean;
  week: number;            // 0..16
  fHealthy: number;
};

export const DEFAULT_PARAMS: ScanParams = {
  callusPct: 50,
  pressureN: 3.5,
  implantLoose: false,
  week: 8,
  fHealthy: F_HEALTHY_HZ,
};

export function paramsFromPatient(p: Patient): ScanParams {
  const last = latestScan(p);
  return {
    callusPct: last.tsiPct,
    pressureN: 3.5,
    implantLoose: false,
    week: last.week,
    fHealthy: F_HEALTHY_HZ,
  };
}

// ---------------------------------------------------------------------------
//  Scan shape + clinical metrics
// ---------------------------------------------------------------------------

export type ClinicalMetrics = {
  tsi: number;                  // %
  rust: number;                 // 4..12 RUST score (matches Streamlit)
  rustCortex: { anterior: number; posterior: number; medial: number; lateral: number };
  fn: number;                   // Hz
  zeta: number;                 // damping ratio
  qFactor: number;              // Q
  mdf: number;                  // modal damping factor (log-decrement / 2pi)
  bandwidthHz: number;          // -3dB bandwidth
  classification: "Stable" | "Delayed Union" | "Non-Union" | "Implant Failure";
  trafficLight: "green" | "amber" | "red";
  recommendation: string;
};

export type Spectrogram = {
  /** rows = freq bins, cols = time slices, values 0..1 */
  data: number[][];
  fMin: number;
  fMax: number;
  tSec: number;
};

export type ScanShape = {
  freqs: number[];
  spectrumInjured: number[];
  spectrumHealthy: number[];
  waveform: number[];
  spectrogram: Spectrogram;
  peakHz: number;
  peakHzHealthy: number;
  secondaryPeakHz: number | null;
  qualityScore: number; // 0..1
  metrics: ClinicalMetrics;
};

// Compute TSI as (f_n / f_healthy) * 100 — matches the Python compute_tsi
function computeTsi(fn: number, fHealthy: number): number {
  return (fn / fHealthy) * 100;
}

// RUST score 4..12 derived from TSI bands (matches Streamlit's logic)
function computeRust(tsi: number): { total: number; cortex: ClinicalMetrics["rustCortex"] } {
  // Map TSI 0..100 to 4 cortex scores of 1..3
  // Each cortex: 1 = no callus, 2 = bridging, 3 = consolidated
  const s = (t: number, offset: number = 0): number => {
    const adj = Math.max(0, Math.min(100, t + offset));
    if (adj >= 75) return 3;
    if (adj >= 40) return 2;
    return 1;
  };
  const cortex = {
    anterior:  s(tsi, +6),
    posterior: s(tsi, -4),
    medial:    s(tsi, +1),
    lateral:   s(tsi, -2),
  };
  const total = cortex.anterior + cortex.posterior + cortex.medial + cortex.lateral;
  return { total, cortex };
}

function classifyHealing(args: {
  tsi: number; zeta: number; implantLoose: boolean; hasSecondary: boolean; week: number;
}): { classification: ClinicalMetrics["classification"]; trafficLight: "green"|"amber"|"red"; recommendation: string } {
  const { tsi, zeta, implantLoose, hasSecondary } = args;
  if (implantLoose && hasSecondary) {
    return {
      classification: "Implant Failure",
      trafficLight: "red",
      recommendation: "Loose hardware detected. Surgical review urgently advised.",
    };
  }
  if (tsi >= 85 || (tsi >= 78 && zeta < 0.05)) {
    return {
      classification: "Stable",
      trafficLight: "green",
      recommendation: "Cleared for full weight-bearing. Follow up in 4 weeks.",
    };
  }
  if (tsi >= 60) {
    return {
      classification: "Delayed Union",
      trafficLight: "amber",
      recommendation: "Partial weight-bearing with crutch / brace. Re-scan in 2 weeks.",
    };
  }
  if (tsi >= 35) {
    return {
      classification: "Delayed Union",
      trafficLight: "amber",
      recommendation: "Touch-down weight-bearing only. Monitor closely.",
    };
  }
  return {
    classification: "Non-Union",
    trafficLight: "red",
    recommendation: "Non-union risk. Escalate to orthopaedic surgeon.",
  };
}

export function buildScan(params: ScanParams): ScanShape {
  const callus = params.callusPct;
  const fn = callusToFrequency(callus, params.fHealthy);
  const zeta = callusToDamping(callus);
  const zetaHealthy = 0.025;

  // pressure quality (matches Python's pressure_quality)
  const pressureQuality = Math.max(0.3, Math.min(1.0,
    1.0 - 0.3 * Math.abs(params.pressureN - 3.5) / 3.5));

  const freqs: number[] = [];
  for (let i = 0; i < SCAN_N_FREQS; i++) {
    const t = i / (SCAN_N_FREQS - 1);
    freqs.push(SCAN_F_MIN + (SCAN_F_MAX - SCAN_F_MIN) * t);
  }

  // Injured spectrum
  const rawInjured = freqs.map((f) => {
    let v = lorentzian(f, fn, zeta);
    if (params.implantLoose) {
      const fnSec = fn * 0.5;
      v += 0.55 * lorentzian(f, fnSec, Math.max(0.02, zeta * 0.8));
    }
    const noise = 0.04 * Math.exp(-f / 800) + 0.01;
    return (v + noise) * pressureQuality;
  });
  const injMax = Math.max(...rawInjured);
  const spectrumInjured = rawInjured.map((v) => v / injMax);

  // Healthy reference spectrum
  const rawHealthy = freqs.map((f) =>
    lorentzian(f, params.fHealthy, zetaHealthy) + 0.04 * Math.exp(-f / 800) + 0.01
  );
  const hMax = Math.max(...rawHealthy);
  const spectrumHealthy = rawHealthy.map((v) => v / hMax);

  // Time-domain waveform (damped sinusoid)
  const omega = 2 * Math.PI * fn;
  const cycles = 8;
  const tEnd = cycles / fn;
  const dt = tEnd / SCAN_WAVEFORM_SAMPLES;
  const wd = omega * Math.sqrt(Math.max(0, 1 - zeta * zeta));
  let waveform: number[] = [];
  for (let i = 0; i < SCAN_WAVEFORM_SAMPLES; i++) {
    const t = i * dt;
    const env = Math.exp(-zeta * omega * t);
    waveform.push(env * Math.sin(wd * t));
  }
  if (params.implantLoose) {
    const fnSec = fn * 0.5;
    const omegaSec = 2 * Math.PI * fnSec;
    const wdSec = omegaSec * Math.sqrt(Math.max(0, 1 - zeta * zeta));
    waveform = waveform.map((v, i) => {
      const t = i * dt;
      const env = Math.exp(-zeta * omegaSec * t);
      return v + 0.5 * env * Math.sin(wdSec * t);
    });
  }
  const wMax = Math.max(...waveform.map((v) => Math.abs(v)));
  const waveformNorm = waveform.map((v) => 0.5 + 0.45 * (v / wMax));

  // Spectrogram — chirp sweep so the peak band lights up over time
  const nT = 56, nF = 40;
  const sgFmin = 20, sgFmax = 1100;
  const sg: number[][] = [];
  for (let r = 0; r < nF; r++) {
    const row: number[] = [];
    const fBin = sgFmin + ((nF - 1 - r) / (nF - 1)) * (sgFmax - sgFmin);
    for (let c = 0; c < nT; c++) {
      const t = c / (nT - 1);
      const chirpF = sgFmin + (sgFmax - sgFmin) * t;
      // gaussian energy around current chirp F + sustained response at fn
      const chirp = Math.exp(-Math.pow((fBin - chirpF) / 80, 2));
      const respEnv = t > 0.05 ? Math.exp(-(t - 0.05) * 4) : 0;
      const resp = respEnv * lorentzian(fBin, fn, Math.max(0.04, zeta));
      row.push(Math.min(1, chirp * 0.7 + resp * 1.6));
    }
    sg.push(row);
  }

  // Detect secondary peak (loose-implant marker)
  let secondaryPeakHz: number | null = null;
  if (params.implantLoose) {
    secondaryPeakHz = fn * 0.5;
  }

  // Q-factor & bandwidth
  const qFactor = 1 / (2 * zeta);
  const bandwidthHz = fn / qFactor;
  // log-decrement / 2pi (real number for SDOF: zeta when small)
  const mdf = (2 * Math.PI * zeta) / Math.sqrt(Math.max(1e-9, 1 - zeta * zeta));

  const tsi = computeTsi(fn, params.fHealthy);
  const rust = computeRust(tsi);
  const cls = classifyHealing({
    tsi, zeta, implantLoose: params.implantLoose,
    hasSecondary: secondaryPeakHz !== null, week: params.week,
  });

  return {
    freqs,
    spectrumInjured,
    spectrumHealthy,
    waveform: waveformNorm,
    spectrogram: { data: sg, fMin: sgFmin, fMax: sgFmax, tSec: SCAN_DURATION_S },
    peakHz: fn,
    peakHzHealthy: params.fHealthy,
    secondaryPeakHz,
    qualityScore: pressureQuality,
    metrics: {
      tsi,
      rust: rust.total,
      rustCortex: rust.cortex,
      fn,
      zeta,
      qFactor,
      mdf,
      bandwidthHz,
      classification: cls.classification,
      trafficLight: cls.trafficLight,
      recommendation: cls.recommendation,
    },
  };
}

// ---------------------------------------------------------------------------
//  Helpers for SVG path generation
// ---------------------------------------------------------------------------

export function pathFromPoints(
  values: number[], width: number, height: number,
  topPad = 4, bottomPad = 4,
): string {
  if (values.length === 0) return "";
  const usableH = height - topPad - bottomPad;
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = topPad + usableH * (1 - v);
      return (i === 0 ? "M" : "L") + x.toFixed(2) + "," + y.toFixed(2);
    })
    .join(" ");
}

export function areaFromPoints(
  values: number[], width: number, height: number,
  topPad = 4, bottomPad = 4,
): string {
  if (values.length === 0) return "";
  const linePath = pathFromPoints(values, width, height, topPad, bottomPad);
  return `${linePath} L${width.toFixed(2)},${(height - bottomPad).toFixed(2)} L0,${(height - bottomPad).toFixed(2)} Z`;
}
