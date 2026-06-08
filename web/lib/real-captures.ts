/**
 * Device capture exhibits per patient.
 *
 * - **Yashas N (P-2611)** — REAL readings measured live from the ResoScan
 *   prototype (ESP32 + ADXL345 @ 800 Hz). Unedited pipeline output.
 * - **Priya / Vikram (P-2742 / P-2810)** — SIMULATED demo captures so all three
 *   patients present a parallel exhibit. Numbers track each one's healing state:
 *   a delayed union rings lower with a duller peak; a non-union is lower and
 *   duller still. Clearly labelled "simulated" — we never pass these off as real.
 *
 * The progression is biomechanically honest:
 *   Yashas (healed)  → 154 Hz, Q≈80, sharp resonance
 *   Priya  (delayed) → 133 Hz, Q≈38, moderate
 *   Vikram (non-union) → 85 Hz, Q≈15, dull / broad
 */

export interface RealCapture {
  press: number;
  fPeakHz: number;
  qFactor: number;
  zeta: number;
  snrDb: number;
}

export interface DeviceData {
  patientCode: string;
  isReal: boolean;          // true = live hardware, false = simulated demo
  device: string;
  fsHz: number;
  samplesPerChirp: number;
  nyquistHz: number;
  captures: RealCapture[];
  best: RealCapture;        // cleanest / highest-Q capture
  note: string;
}

// ── Yashas N — REAL hardware ──────────────────────────────────────────────────
const YASHAS: DeviceData = {
  patientCode: "P-2611",
  isReal: true,
  device: "ESP32 + ADXL345 (CP2102 @ COM5)",
  fsHz: 800,
  samplesPerChirp: 800,
  nyquistHz: 400,
  captures: [
    { press: 1, fPeakHz: 73.7, qFactor: 34.5, zeta: 0.0145, snrDb: 3.5 },
    { press: 2, fPeakHz: 51.4, qFactor: 1.3, zeta: 0.3747, snrDb: 8.9 },
    { press: 3, fPeakHz: 154.2, qFactor: 79.5, zeta: 0.0063, snrDb: 19.5 },
  ],
  best: { press: 3, fPeakHz: 154.2, qFactor: 79.5, zeta: 0.0063, snrDb: 19.5 },
  note:
    "Raw readings span 51–154 Hz across presses — soft-tissue coupling + contact " +
    "force vary each time. That raw swing is the exact problem normalization solves: " +
    "average N sweeps (+√N SNR), band-pass, sub-bin peak → one stable value.",
};

// ── Priya Iyer — SIMULATED (delayed union, smoker) ───────────────────────────
const PRIYA: DeviceData = {
  patientCode: "P-2742",
  isReal: false,
  device: "Simulated ESP32 + ADXL345 (demo patient)",
  fsHz: 800,
  samplesPerChirp: 800,
  nyquistHz: 400,
  captures: [
    { press: 1, fPeakHz: 108.5, qFactor: 22.0, zeta: 0.0180, snrDb: 11.0 },
    { press: 2, fPeakHz: 89.2, qFactor: 15.5, zeta: 0.0250, snrDb: 9.5 },
    { press: 3, fPeakHz: 132.6, qFactor: 38.0, zeta: 0.0120, snrDb: 14.5 },
  ],
  best: { press: 3, fPeakHz: 132.6, qFactor: 38.0, zeta: 0.0120, snrDb: 14.5 },
  note:
    "Simulated delayed-union captures. The resonance is lower and the peak less " +
    "sharp than a healed bone — consistent with a softer callus. Same normalization " +
    "pipeline turns the raw spread into one stable TSI.",
};

// ── Vikram Singh — SIMULATED (non-union) ─────────────────────────────────────
const VIKRAM: DeviceData = {
  patientCode: "P-2810",
  isReal: false,
  device: "Simulated ESP32 + ADXL345 (demo patient)",
  fsHz: 800,
  samplesPerChirp: 800,
  nyquistHz: 400,
  captures: [
    { press: 1, fPeakHz: 58.3, qFactor: 9.5, zeta: 0.0400, snrDb: 7.0 },
    { press: 2, fPeakHz: 71.4, qFactor: 12.0, zeta: 0.0340, snrDb: 8.5 },
    { press: 3, fPeakHz: 84.7, qFactor: 14.5, zeta: 0.0290, snrDb: 9.8 },
  ],
  best: { press: 3, fPeakHz: 84.7, qFactor: 14.5, zeta: 0.0290, snrDb: 9.8 },
  note:
    "Simulated non-union captures. Low frequency and a dull, broad peak (low Q) — " +
    "the signature of a fracture that has not bridged. Even here, normalization " +
    "yields a stable, repeatable number the surgeon can trust.",
};

const BY_CODE: Record<string, DeviceData> = {
  "P-2611": YASHAS,
  "P-2742": PRIYA,
  "P-2810": VIKRAM,
};

/** Back-compat export (Yashas' real data). */
export const REAL_DEVICE_DATA = YASHAS;

/** Device capture exhibit for a patient, or undefined if none. */
export function getDeviceData(patientCode: string): DeviceData | undefined {
  return BY_CODE[patientCode];
}

/** True if this patient has a capture exhibit (all three demo patients do). */
export function hasRealCaptures(patientCode: string): boolean {
  return patientCode in BY_CODE;
}
