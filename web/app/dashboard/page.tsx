"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import type { ApiPatient, ApiScanDetail } from "@/lib/api";
import { api } from "@/lib/api";
import { PATIENTS } from "@/lib/patients";

import { FadeIn } from "@/components/ui/motion";
import { SubviewTabs } from "@/components/dashboard/subview-tabs";
import { DeviceChip } from "@/components/dashboard/device-chip";
import { ScanView } from "@/components/dashboard/views/scan-view";
import { NormalizationView } from "@/components/dashboard/views/normalization-view";
import { StatusView } from "@/components/dashboard/views/status-view";
import { ReportView } from "@/components/dashboard/views/report-view";
import { TrendView } from "@/components/dashboard/views/trend-view";
import { ModelView } from "@/components/dashboard/views/model-view";
import { KnowledgeGraphView } from "@/components/dashboard/views/knowledge-graph-view";

function offlinePatient(code: string): ApiPatient {
  const p = PATIENTS.find((x) => x.key === code || x.id === code) ?? PATIENTS[0];
  const last = p.scans[p.scans.length - 1];
  return {
    id: p.key === "arjun" ? 1 : p.key === "priya" ? 2 : 3,
    patientCode: p.id, name: p.name, age: p.age, sex: p.sex,
    smoker: p.smoker, diabetic: p.diabetic, bmi: p.bmi, bone: p.bone,
    fractureType: p.fractureType, fractureDate: p.fractureDate,
    hospital: p.hospital, surgeon: p.surgeon, status: p.status,
    latestTsi: last?.tsiPct ?? null, latestWeek: last?.week ?? null,
    scanCount: p.scans.length,
  };
}

function statusColor(s: string | null) {
  if (s === "cleared") return "var(--safe)";
  if (s === "delayed") return "var(--caution)";
  return "var(--danger)";
}

function DashboardInner() {
  const params = useSearchParams();
  const isOffline = params.get("demo") === "offline";
  const patientParam = params.get("patient") ?? "P-2611";
  const view = params.get("view") ?? "scan";

  const [patient, setPatient] = useState<ApiPatient | null>(null);
  const [scanId, setScanId] = useState<number | null>(null);
  const [lastScan, setLastScan] = useState<ApiScanDetail | null>(null);
  const [toast, setToast] = useState<{ id: number; tsi: number | null; source: string } | null>(null);

  const refreshPatient = useCallback(() => {
    if (isOffline) { setPatient(offlinePatient(patientParam)); return; }
    api.patients()
      .then((list) => {
        const found =
          list.find((p) => p.patientCode === patientParam) ??
          list.find((p) => p.id.toString() === patientParam) ??
          list[0];
        setPatient(found ?? offlinePatient(patientParam));
      })
      .catch(() => setPatient(offlinePatient(patientParam)));
  }, [patientParam, isOffline]);

  useEffect(() => { refreshPatient(); }, [refreshPatient]);

  // Reset scan when patient changes
  useEffect(() => { setScanId(null); setLastScan(null); }, [patientParam]);

  const handleScanCreated = useCallback((id: number, scan: ApiScanDetail) => {
    setScanId(id);
    setLastScan(scan);
    // Reflect the newly-stored scan live across the whole dashboard: refresh this
    // patient's header, and broadcast so the rail (and any listener) re-fetches.
    refreshPatient();
    setToast({ id, tsi: scan.tsiPct, source: scan.source });
    window.setTimeout(() => setToast((t) => (t && t.id === id ? null : t)), 3500);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("reso:scan-created", { detail: { id, scan } }));
    }
  }, [refreshPatient]);

  if (!patient) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-[13px] animate-pulse">
        Loading patient…
      </div>
    );
  }

  const toneColor = statusColor(patient.status);

  return (
    <div className="flex h-full flex-col">

      {/* Live "scan stored" pop */}
      {toast && (
        <div
          className="pointer-events-none fixed right-5 top-5 z-50 flex items-center gap-2 rounded-lg border px-4 py-2.5 shadow-lg"
          style={{ borderColor: "rgba(0,255,170,0.35)", background: "rgba(0,40,36,0.95)" }}
        >
          <span className="h-2 w-2 rounded-full" style={{ background: "var(--accent)" }} />
          <span className="text-[12.5px] text-text">
            <span style={{ color: "var(--accent)" }}>
              {toast.source === "device" ? "Live scan stored" : "Scan stored"}
            </span>
            {" "}· #{toast.id}
            {toast.tsi != null && <> · {Math.round(toast.tsi)}% healing index</>}
          </span>
        </div>
      )}

      {/* Patient detail header */}
      <div className="flex items-center gap-4 border-b border-line px-5 py-3">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold"
          style={{ background: toneColor, color: "#001619" }}
        >
          {patient.name.split(" ").map((s) => s[0]).join("")}
        </div>
        <div className="leading-tight">
          <div className="font-display text-[14px] font-semibold text-text">{patient.name}</div>
          <div className="text-[11px] text-text-muted">
            {patient.patientCode} · {patient.age} yr · {patient.sex} ·{" "}
            {patient.fractureType} fracture · {patient.bone}
          </div>
        </div>
        {lastScan && (
          <div className="ml-auto flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: toneColor }} />
            <span className="font-mono text-[12px]" style={{ color: toneColor }}>
              {lastScan.tsiPct != null ? Math.round(lastScan.tsiPct) : "—"}% TSI · scan #{lastScan.id}
            </span>
          </div>
        )}
      </div>

      {/* Sub-view tabs */}
      <SubviewTabs rightSlot={<DeviceChip />} hasScan={scanId != null} />

      {/* Content area — subtle reveal on each view switch */}
      <div className="flex-1 overflow-auto">
        <FadeIn key={view} className="min-h-full">
          {view === "scan" && (
            <ScanView patient={patient} onScanCreated={handleScanCreated} offline={isOffline} />
          )}
          {view === "normalization" && (
            <NormalizationView scanId={scanId} offline={isOffline} />
          )}
          {view === "status" && <StatusView patient={patient} scan={lastScan} />}
          {view === "graph" && <KnowledgeGraphView patient={patient} scanId={scanId} />}
          {view === "report" && (
            <ReportView patient={patient} scan={lastScan} scanId={scanId} />
          )}
          {view === "trend" && <TrendView patient={patient} />}
          {view === "model" && <ModelView />}
        </FadeIn>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted animate-pulse">Loading…</div>}>
      <DashboardInner />
    </Suspense>
  );
}
