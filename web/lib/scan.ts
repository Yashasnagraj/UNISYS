/**
 * Client-side scan signal generator. No FFT, no Welch, no scipy — instead
 * we derive a Lorentzian peak shape parameterised on the patient's current
 * resonant frequency (f_n) and damping (zeta). Visually indistinguishable
 * from a real PSD curve for a single-DOF damped oscillator.
 *
 *  Lorentzian (normalised peak):
 *      L(f) = 1 / sqrt( (1 - (f/fn)^2)^2 + (2*zeta*(f/fn))^2 )
 *
 * Plus a damped sinusoid for the time-domain waveform:
 *      x(t) = A * exp(-zeta*omega*t) * sin(omega * sqrt(1-zeta^2) * t)
 */

import { latestScan, type Patient } from "./patients";

export const SCAN_F_MIN = 20;
export const SCAN_F_MAX = 1100;
export const SCAN_N_FREQS = 220;
export const SCAN_WAVEFORM_SAMPLES = 280;

export type ScanShape = {
  /** frequency axis Hz */
  freqs: number[];
  /** spectral magnitude 0..1 */
  spectrum: number[];
  /** peak frequency (highest point) */
  peakHz: number;
  /** time-domain waveform 0..1 (centred at 0.5) */
  waveform: number[];
  /** confidence percent (used for the confidence bar; from prediction) */
  qualityScore: number; // 0..1
  /** patient's healing state */
  tsi: number;
  zeta: number;
  fn: number;
};

function lorentzian(f: number, fn: number, zeta: number): number {
  const ratio = f / fn;
  const denom = Math.sqrt(
    Math.pow(1 - ratio * ratio, 2) + Math.pow(2 * zeta * ratio, 2)
  );
  return 1 / denom;
}

export function buildScanShape(p: Patient): ScanShape {
  const last = latestScan(p);
  const fn = last.fnHz;
  // Re-tune zeta slightly so the visual peak is clearly sharper for healed bone
  const zeta = Math.max(0.025, Math.min(0.2, last.zeta));

  // Frequency grid (log-ish so we resolve the low end nicely)
  const freqs: number[] = [];
  for (let i = 0; i < SCAN_N_FREQS; i++) {
    const t = i / (SCAN_N_FREQS - 1);
    freqs.push(SCAN_F_MIN + (SCAN_F_MAX - SCAN_F_MIN) * t);
  }

  // Lorentzian peak + small high-frequency noise floor
  const raw = freqs.map((f) => {
    const peak = lorentzian(f, fn, zeta);
    // a gentle 1/f noise floor + tiny stochastic ripple seeded deterministically
    const noise = 0.04 * Math.exp(-f / 800) + 0.01;
    return peak + noise;
  });

  // Normalise to 0..1 (so the chart auto-scales nicely)
  const max = Math.max(...raw);
  const spectrum = raw.map((v) => v / max);

  // Damped sinusoid waveform — uses fn as the carrier
  // sample over ~6 cycles
  const cycles = 6;
  const omega = 2 * Math.PI * fn;
  const tEnd = cycles / fn;
  const dt = tEnd / SCAN_WAVEFORM_SAMPLES;
  const wd = omega * Math.sqrt(Math.max(0, 1 - zeta * zeta));
  const waveform: number[] = [];
  for (let i = 0; i < SCAN_WAVEFORM_SAMPLES; i++) {
    const t = i * dt;
    const env = Math.exp(-zeta * omega * t);
    const v = env * Math.sin(wd * t);
    waveform.push(v);
  }

  // Map waveform to 0..1 around 0.5
  const wMax = Math.max(...waveform.map(Math.abs));
  const waveformNorm = waveform.map((v) => 0.5 + 0.45 * (v / wMax));

  // Quality score derived from peak sharpness (higher Q-factor = cleaner scan)
  // Lorentzian half-power bandwidth ≈ 2 * zeta * fn ; sharper peak = better
  const q = 1 / (2 * zeta);
  const qualityScore = Math.max(0.5, Math.min(1.0, (q - 2) / 14));

  return {
    freqs,
    spectrum,
    peakHz: fn,
    waveform: waveformNorm,
    qualityScore,
    tsi: last.tsiPct,
    zeta,
    fn,
  };
}

/** Build an SVG path "d" attribute from a series of points. */
export function pathFromPoints(
  values: number[],
  width: number,
  height: number,
  topPad = 4,
  bottomPad = 4,
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

/** Build a closed area path with a baseline at y=height (for filled area). */
export function areaFromPoints(
  values: number[],
  width: number,
  height: number,
  topPad = 4,
  bottomPad = 4,
): string {
  if (values.length === 0) return "";
  const linePath = pathFromPoints(values, width, height, topPad, bottomPad);
  return `${linePath} L${width.toFixed(2)},${(height - bottomPad).toFixed(2)} L0,${(height - bottomPad).toFixed(2)} Z`;
}
