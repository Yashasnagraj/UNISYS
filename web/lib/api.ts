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
};
