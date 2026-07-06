/**
 * Typed client for the ResoScan FastAPI backend.
 * Falls back gracefully — callers check for errors rather than crashing.
 */

const BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── API shapes (camelCase mirrors FastAPI's alias_generator=to_camel) ────────

export interface ApiPatient {
  id: number;
  patientCode: string;
  name: string;
  age: number;
  sex: string;
  smoker: boolean;
  diabetic: boolean;
  bmi: number | null;
  bone: string;
  fractureType: string;
  fractureDate: string;
  hospital: string | null;
  surgeon: string | null;
  status: string | null;
  latestTsi: number | null;
  latestWeek: number | null;
  scanCount: number;
}

export interface ApiScanDetail {
  id: number;
  patientId: number;
  scanDate: string;
  week: number;
  source: string;
  fPeakHz: number | null;
  fHealthyHz: number | null;
  tsiPct: number | null;
  tsiPctLinear: number | null;
  zeta: number | null;
  qFactor: number | null;
  bandwidthHz: number | null;
  predictedLabel: string | null;
  confidence: number | null;
  trafficLight: string | null;
  recommendation: string | null;
  snrDb: number | null;
  snrGainDb: number | null;
  tsiStdRaw: number | null;
  tsiStdNorm: number | null;
  improvementFactor: number | null;
}

export interface ApiStage {
  name: string;
  note: string;
  signal: number[];
}

export interface ApiNormalization {
  scanId: number;
  stages: ApiStage[];
  freqs: number[];
  psdDb: number[];
  fPeakHz: number;
  snrDbRaw: number;
  snrDbNorm: number;
  snrGainDb: number;
}

export interface ApiRepeatability {
  scanId: number;
  nSweeps: number;
  fHealthyHz: number;
  tsiRawPerSweep: number[];
  tsiNormPerSweep: number[];
  tsiStdRaw: number;
  tsiStdNorm: number;
  tsiCvRaw: number;
  tsiCvNorm: number;
  improvementFactor: number;
  snrGainDb: number;
}

export interface ApiDeviceStatus {
  connected: boolean;
  port: string | null;
  baud: number;
  description: string;
}

// ── Knowledge graph / causal / human-in-the-loop ─────────────────────────────

export interface ApiSimilarCase {
  scanId: number;
  patientId: number;
  patientCode: string | null;
  patientName: string | null;
  week: number;
  tsiPct: number | null;
  predictedLabel: string | null;
  confirmedOutcome: string | null;
  comorbidities: string[];
  distance: number;
  score: number;
  hasOutcome: boolean;
}

export interface ApiSimilarCases {
  scanId: number;
  cases: ApiSimilarCase[];
}

export interface ApiCausalFactor {
  factor: string;
  value: string;
  sign: number;
  weight: number;
  citation: string;
}

export interface ApiCausalExplanation {
  scanId: number;
  verdict: string;
  nSimilar: number;
  activeFactors: ApiCausalFactor[];
  narrative: string;
}

export interface ApiGraphNode {
  id: string;
  type: string;
  label?: string;
  [k: string]: unknown;
}

export interface ApiGraphEdge {
  source: string;
  target: string;
  type: string;
  [k: string]: unknown;
}

export interface ApiEgoGraph {
  patientId: number;
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
}

export interface ApiModelVersion {
  id: number;
  version: number;
  syntheticN: number;
  clinicianPairs: number;
  macroF1Holdout: number;
  championF1: number | null;
  promoted: boolean;
  isActive: boolean;
  notes: string | null;
  createdAt: string | null;
}

export interface ApiModelVersions {
  activeVersion: number | null;
  versions: ApiModelVersion[];
}

export interface ApiRetrainResult {
  championF1: number;
  challengerF1: number;
  promoted: boolean;
  newVersion: number;
  clinicianPairs: number;
  syntheticN: number;
}

export interface ApiConfirmResponse {
  scanId: number;
  feedbackId: number;
  agree: boolean;
  overrideLabel: string | null;
}

export interface ApiOutcomeResponse {
  outcomeId: number;
  patientId: number;
  scanId: number | null;
  trueLabel: string;
}

// ── Fetch helpers ─────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(
      (err as { detail?: string }).detail ?? `${r.status} ${path}`,
    );
  }
  return r.json() as Promise<T>;
}

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  patients: () => apiFetch<ApiPatient[]>("/api/patients"),

  patientDetail: (code: string) =>
    apiFetch<ApiPatient & { scans: ApiScanDetail[] }>(`/api/patients/${code}`),

  scan: (id: number) => apiFetch<ApiScanDetail>(`/api/scans/${id}`),

  normalization: (id: number) =>
    apiFetch<ApiNormalization>(`/api/scans/${id}/normalization`),

  repeatability: (id: number) =>
    apiFetch<ApiRepeatability>(`/api/scans/${id}/repeatability`),

  deviceStatus: () => apiFetch<ApiDeviceStatus>("/api/device/status"),

  createScan: (body: {
    source: "sim" | "device" | "upload";
    patientId: number;
    week?: number;
    callusPct?: number;
    nSweeps?: number;
    port?: string | null;
    samples?: number[];
    fs?: number;
  }) =>
    apiFetch<ApiScanDetail>("/api/scans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  similar: (id: number, k = 5) =>
    apiFetch<ApiSimilarCases>(`/api/scans/${id}/similar?k=${k}`),

  causal: (id: number) =>
    apiFetch<ApiCausalExplanation>(`/api/scans/${id}/causal`),

  patientGraph: (patientId: number) =>
    apiFetch<ApiEgoGraph>(`/api/graph/patient/${patientId}`),

  confirmScan: (id: number, body: {
    agree: boolean; overrideLabel?: string | null;
    clinician?: string | null; notes?: string | null;
  }) =>
    apiFetch<ApiConfirmResponse>(`/api/scans/${id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  recordOutcome: (id: number, body: {
    trueLabel: string; weeksToWalk?: number | null; rust16w?: number | null;
  }) =>
    apiFetch<ApiOutcomeResponse>(`/api/scans/${id}/outcome`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  modelVersions: () => apiFetch<ApiModelVersions>("/api/model/versions"),

  retrain: () =>
    apiFetch<ApiRetrainResult>("/api/model/retrain", { method: "POST" }),
};
