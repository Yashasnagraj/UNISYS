"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Home } from "lucide-react";
import { cn } from "@/lib/utils";
import { Wordmark } from "@/components/brand/wordmark";
import type { ApiPatient } from "@/lib/api";
import { api } from "@/lib/api";
import { PATIENTS } from "@/lib/patients"; // offline fallback

// ── colour helpers ────────────────────────────────────────────────────────────

function statusColor(status: string | null) {
  if (status === "cleared") return "var(--safe)";
  if (status === "delayed") return "var(--caution)";
  return "var(--danger)";
}

function tsiColor(tsi: number | null) {
  if (tsi == null) return "var(--text-muted)";
  if (tsi >= 64) return "var(--safe)";
  if (tsi >= 30) return "var(--caution)";
  return "var(--danger)";
}

// ── offline fallback patient list ─────────────────────────────────────────────

function offlinePatients(): ApiPatient[] {
  return PATIENTS.map((p) => {
    const last = p.scans[p.scans.length - 1];
    return {
      id: p.key === "arjun" ? 1 : p.key === "priya" ? 2 : 3,
      patientCode: p.id,
      name: p.name,
      age: p.age,
      sex: p.sex,
      smoker: p.smoker,
      diabetic: p.diabetic,
      bmi: p.bmi,
      bone: p.bone,
      fractureType: p.fractureType,
      fractureDate: p.fractureDate,
      hospital: p.hospital,
      surgeon: p.surgeon,
      status: p.status,
      latestTsi: last?.tsiPct ?? null,
      latestWeek: last?.week ?? null,
      scanCount: p.scans.length,
    };
  });
}

// ── component ─────────────────────────────────────────────────────────────────

export function PatientRail() {
  const router = useRouter();
  const params = useSearchParams();
  const isOffline = params.get("demo") === "offline";
  const selectedCode = params.get("patient") ?? "";

  const [patients, setPatients] = useState<ApiPatient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOffline) {
      setPatients(offlinePatients());
      setLoading(false);
      return;
    }
    api.patients()
      .then(setPatients)
      .catch(() => setPatients(offlinePatients()))
      .finally(() => setLoading(false));
  }, [isOffline]);

  function select(code: string) {
    const sp = new URLSearchParams(params.toString());
    sp.set("patient", code);
    sp.delete("scanId"); // clear cached scan when switching patient
    router.replace(`/dashboard?${sp.toString()}`, { scroll: false });
  }

  return (
    <aside className="hidden md:flex w-[200px] shrink-0 flex-col border-r border-line bg-bg-panel">
      {/* Logo */}
      <div className="flex items-center justify-center py-5 border-b border-line">
        <Link href="/" aria-label="Back to landing">
          <Wordmark className="scale-90" />
        </Link>
      </div>

      {/* Patient list */}
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto py-3 px-2">
        <div className="px-2 pb-1 text-[10px] uppercase tracking-[0.16em] text-text-faint">
          Patients
        </div>

        {loading && (
          <div className="px-3 py-2 text-[12px] text-text-faint animate-pulse">
            Loading…
          </div>
        )}

        {patients.map((p) => {
          const active =
            selectedCode === p.patientCode ||
            selectedCode === p.id.toString() ||
            (!selectedCode && p.id === 1);
          const color = statusColor(p.status);
          return (
            <button
              key={p.patientCode}
              onClick={() => select(p.patientCode)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors w-full",
                active
                  ? "bg-bg-card text-text"
                  : "text-text-muted hover:bg-bg-card hover:text-text",
              )}
            >
              {/* Status dot */}
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: color }}
              />
              {/* Name + TSI */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-[12px] font-medium leading-tight">
                    {p.name.split(" ")[0]}
                  </span>
                  {/* Real-device vs simulation tag */}
                  <span
                    className="shrink-0 rounded px-1 py-px text-[8px] font-semibold uppercase tracking-wide"
                    style={
                      p.patientCode === "P-2611"
                        ? { background: "rgba(0,255,170,0.15)", color: "var(--accent)" }
                        : { background: "rgba(255,255,255,0.06)", color: "var(--text-faint)" }
                    }
                    title={
                      p.patientCode === "P-2611"
                        ? "Real device measurements (ESP32 + ADXL345)"
                        : "Simulated patient — example trajectory"
                    }
                  >
                    {p.patientCode === "P-2611" ? "real" : "sim"}
                  </span>
                </div>
                <div
                  className="font-mono text-[10px] leading-tight"
                  style={{ color: tsiColor(p.latestTsi) }}
                >
                  {p.latestTsi != null ? `${Math.round(p.latestTsi)}%` : "—"}
                </div>
              </div>
              {/* Active indicator */}
              {active && (
                <span
                  className="absolute left-0 top-1 bottom-1 w-[2px] rounded-full"
                  style={{ background: "var(--accent)" }}
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-line px-3 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 text-[11px] text-text-faint hover:text-text transition-colors"
        >
          <Home size={13} strokeWidth={1.6} />
          Landing
        </Link>
      </div>
    </aside>
  );
}
