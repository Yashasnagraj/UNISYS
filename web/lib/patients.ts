/**
 * Patient registry — mirrors ortho_simulator/data/demo_patients.py.
 *
 * Three demo patients with dense scan histories generated from a Gompertz
 * trajectory with biologically plausible measurement noise. The narrative
 * triptych: green (cleared), amber (delayed), red (non-union risk).
 */

export type PatientStatus = "cleared" | "delayed" | "non-union";

export type Scan = {
  /** ISO date string yyyy-mm-dd */
  date: string;
  /** weeks since fracture */
  week: number;
  /** measured resonant frequency in Hz */
  fnHz: number;
  /** tibial stiffness index 0..100 */
  tsiPct: number;
  /** damping ratio */
  zeta: number;
  /** clinical verdict on the day */
  classification: "Stable" | "Delayed Union" | "Non-Union";
};

export type Patient = {
  id: string;            // P-2611 etc.
  key: string;           // dropdown key matching Python
  name: string;
  age: number;
  sex: "M" | "F";
  smoker: boolean;
  diabetic: boolean;
  bmi: number;
  bone: "Tibia";
  fractureType: "Transverse" | "Oblique" | "Comminuted";
  /** ISO yyyy-mm-dd */
  fractureDate: string;
  hospital: string;
  surgeon: string;
  scans: Scan[];
  /** narrative status — drives colour and triptych */
  status: PatientStatus;
};

// Pinned reference date — matches TODAY in demo_patients.py
export const TODAY_ISO = "2026-05-20";
export const TODAY_DATE = new Date(TODAY_ISO + "T00:00:00Z");

// --- Internal helpers (mirror demo_patients.py:_generate_scans) ----------

const F_HEALTHY_HZ = 850.0;
const F_BASELINE_HZ = 300.0;
const TSI_TO_FN_RANGE = F_HEALTHY_HZ - F_BASELINE_HZ;

function gompertz(weeks: number, k: number, t0: number): number {
  return 100 * Math.exp(-Math.exp(-k * (weeks - t0)));
}

function classify(tsi: number): "Stable" | "Delayed Union" | "Non-Union" {
  if (tsi >= 75) return "Stable";
  if (tsi >= 40) return "Delayed Union";
  return "Non-Union";
}

function zetaFromTsi(tsi: number): number {
  // matches engine.signal_generator: zeta = 0.20 - 0.175 * (tsi/100)^1.3
  return 0.20 - 0.175 * Math.pow(tsi / 100, 1.3);
}

function fnFromTsi(tsi: number): number {
  return F_BASELINE_HZ + TSI_TO_FN_RANGE * (tsi / 100);
}

/** Mulberry32 — small deterministic RNG so JS output matches across machines */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Box-Muller standard normal sample */
function gaussian(rng: () => number): number {
  let u = 0, v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function generateScans(opts: {
  fractureDateIso: string;
  weeksObserved: number;
  k: number;
  t0: number;
  noisePct: number;
  seed: number;
  earlyCadenceDays?: number;
  lateCadenceDays?: number;
  earlyWindowWeeks?: number;
}): Scan[] {
  const {
    fractureDateIso,
    weeksObserved,
    k,
    t0,
    noisePct,
    seed,
    earlyCadenceDays = 3,
    lateCadenceDays = 7,
    earlyWindowWeeks = 4.0,
  } = opts;

  const rng = mulberry32(seed);
  const daysTotal = Math.round(weeksObserved * 7);
  const earlyDays = Math.round(earlyWindowWeeks * 7);

  const days: number[] = [];
  let d = 0;
  while (d <= daysTotal) {
    days.push(d);
    d += d < earlyDays ? earlyCadenceDays : lateCadenceDays;
  }
  if (days[days.length - 1] !== daysTotal) days.push(daysTotal);

  const out: Scan[] = [];
  for (const day of days) {
    const w = day / 7.0;
    const tsiClean = gompertz(w, k, t0);
    const sigma = noisePct * (1.0 + 0.5 * (1.0 - tsiClean / 100));
    const tsiNoisy = Math.min(99.9, Math.max(0.5, tsiClean + gaussian(rng) * sigma));
    out.push({
      date: addDays(fractureDateIso, day),
      week: +w.toFixed(2),
      fnHz: +fnFromTsi(tsiNoisy).toFixed(1),
      tsiPct: +tsiNoisy.toFixed(1),
      zeta: +zetaFromTsi(tsiNoisy).toFixed(3),
      classification: classify(tsiNoisy),
    });
  }
  return out;
}

// --- Patients ------------------------------------------------------------

const arjunFracture = addDays(TODAY_ISO, -(8 * 7 + 2));
const priyaFracture = addDays(TODAY_ISO, -(10 * 7));
const vikramFracture = addDays(TODAY_ISO, -(12 * 7));

export const PATIENTS: Patient[] = [
  {
    id: "P-2611",
    key: "arjun",
    name: "Arjun Mehta",
    age: 28,
    sex: "M",
    smoker: false,
    diabetic: false,
    bmi: 24.1,
    bone: "Tibia",
    fractureType: "Transverse",
    fractureDate: arjunFracture,
    hospital: "Ramaiah Memorial Hospital",
    surgeon: "Dr. R. Krishnan",
    status: "cleared",
    scans: generateScans({
      fractureDateIso: arjunFracture,
      weeksObserved: (Date.parse(TODAY_ISO) - Date.parse(arjunFracture)) / (1000 * 60 * 60 * 24 * 7),
      k: 0.48, t0: 4.0, noisePct: 2.2, seed: 11,
    }),
  },
  {
    id: "P-2742",
    key: "priya",
    name: "Priya Iyer",
    age: 45,
    sex: "F",
    smoker: true,
    diabetic: false,
    bmi: 27.8,
    bone: "Tibia",
    fractureType: "Oblique",
    fractureDate: priyaFracture,
    hospital: "Ramaiah Memorial Hospital",
    surgeon: "Dr. S. Patel",
    status: "delayed",
    scans: generateScans({
      fractureDateIso: priyaFracture,
      weeksObserved: (Date.parse(TODAY_ISO) - Date.parse(priyaFracture)) / (1000 * 60 * 60 * 24 * 7),
      k: 0.30, t0: 6.5, noisePct: 2.5, seed: 27,
    }),
  },
  {
    id: "P-2810",
    key: "vikram",
    name: "Vikram Singh",
    age: 67,
    sex: "M",
    smoker: true,
    diabetic: true,
    bmi: 30.2,
    bone: "Tibia",
    fractureType: "Comminuted",
    fractureDate: vikramFracture,
    hospital: "Ramaiah Memorial Hospital",
    surgeon: "Dr. R. Krishnan",
    status: "non-union",
    scans: generateScans({
      fractureDateIso: vikramFracture,
      weeksObserved: (Date.parse(TODAY_ISO) - Date.parse(vikramFracture)) / (1000 * 60 * 60 * 24 * 7),
      k: 0.06, t0: 18.0, noisePct: 1.4, seed: 42,
    }),
  },
];

export function getPatient(key: string): Patient {
  return PATIENTS.find((p) => p.key === key) ?? PATIENTS[0];
}

export function statusColor(s: PatientStatus): string {
  return s === "cleared" ? "var(--safe)" : s === "delayed" ? "var(--caution)" : "var(--danger)";
}

export function statusLabel(s: PatientStatus): string {
  return s === "cleared" ? "Cleared" : s === "delayed" ? "Delayed" : "Non-union risk";
}

/** convenience: latest scan */
export function latestScan(p: Patient): Scan {
  return p.scans[p.scans.length - 1];
}
