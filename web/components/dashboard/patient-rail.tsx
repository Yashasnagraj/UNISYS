"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Home } from "lucide-react";
import { cn } from "@/lib/utils";
import { Wordmark } from "@/components/brand/wordmark";
import { Badge } from "@/components/ui/badge";
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
    const load = () =>
      api.patients()
        .then(setPatients)
        .catch(() => setPatients(offlinePatients()))
        .finally(() => setLoading(false));
    load();
    // Re-fetch whenever a scan is stored, so the live TSI % updates in the rail.
    const onScan = () => load();
    window.addEventListener("reso:scan-created", onScan);
    return () => window.removeEventListener("reso:scan-created", onScan);
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
                "relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left w-full",
                "transition-all duration-150",
                active
                  ? "bg-bg-card text-text"
                  : "text-text-muted hover:bg-bg-elevated hover:text-text hover:translate-x-0.5",
              )}
              style={active ? { boxShadow: "inset 2px 0 0 var(--accent)" } : undefined}
            >
              {/* Status dot with ring */}
              <span className="relative flex h-3 w-3 shrink-0 items-center justify-center">
                <span className="absolute inset-0 rounded-full opacity-30" style={{ background: color }} />
                <span className="h-2 w-2 rounded-full" style={{ background: color }} />
              </span>
              {/* Name + TSI */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-[12px] font-medium leading-tight">
                    {p.name.split(" ")[0]}
                  </span>
                  <Badge
                    tone={p.patientCode === "P-2611" ? "accent" : "neutral"}
                    className="shrink-0 px-1 py-px text-[8px]"
                  >
                    {p.patientCode === "P-2611" ? "real" : "sim"}
                  </Badge>
                </div>
                <div className="font-mono text-[10px] leading-tight" style={{ color: tsiColor(p.latestTsi) }}>
                  {p.latestTsi != null ? `${Math.round(p.latestTsi)}%` : "—"}
                </div>
              </div>
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
