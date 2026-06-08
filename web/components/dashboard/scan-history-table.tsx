"use client";

/**
 * Scan history table — the "everything is real" proof.
 *
 * Fetches the patient's full scan list from GET /api/patients/{code} and renders
 * every measurement with its exact timestamp. All values come straight from the
 * backend normalization pipeline (f_peak, TSI, ζ, SNR, jitter). Nothing faked.
 *
 * The most-recent row is highlighted; the timestamp column makes it obvious each
 * scan is a distinct, live event.
 */

import { useEffect, useState } from "react";
import { Clock, Database } from "lucide-react";
import { api, type ApiScanDetail } from "@/lib/api";
import { InfoTip } from "@/components/ui/info-tip";

interface ScanRow extends ApiScanDetail {
  createdAt?: string | null;   // ScanRead exposes this; ApiScanDetail does not
}

function fmtTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.includes("T") ? iso : iso.replace(" ", "T") + "Z");
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

function fmt(v: number | null | undefined, d = 1): string {
  return v == null ? "—" : v.toFixed(d);
}

function lightColor(t: string | null) {
  if (t === "green") return "var(--safe)";
  if (t === "amber") return "var(--caution)";
  return "var(--danger)";
}

function sourceBadge(src: string) {
  const isDevice = src === "device";
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide"
      style={{
        background: isDevice ? "rgba(0,255,170,0.12)" : "rgba(255,255,255,0.06)",
        color: isDevice ? "var(--accent)" : "var(--text-faint)",
      }}
    >
      {src}
    </span>
  );
}

interface Props {
  patientCode: string;
  /** Highlight the row with this scan id (the just-run scan) */
  highlightScanId?: number | null;
  /** Refresh trigger — bump to re-fetch after a new scan */
  refreshKey?: number;
}

export function ScanHistoryTable({ patientCode, highlightScanId, refreshKey }: Props) {
  const [scans, setScans] = useState<ScanRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.patientDetail(patientCode)
      .then((d) => {
        const list = (d.scans ?? []) as ScanRow[];
        // newest first
        setScans([...list].reverse());
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [patientCode, refreshKey]);

  return (
    <div className="surface overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <div className="flex items-center gap-2">
          <Database size={14} className="text-accent" strokeWidth={1.7} />
          <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
            Measurement Log
          </span>
        </div>
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-text-faint">
          <Clock size={11} />
          {scans.length} records · SQLite
        </span>
      </div>

      {loading && (
        <div className="px-5 py-6 text-[12px] text-text-faint animate-pulse">Loading history…</div>
      )}
      {error && (
        <div className="px-5 py-6 text-[12px]" style={{ color: "var(--caution)" }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr className="border-b border-line text-left text-[10px] uppercase tracking-wide text-text-faint">
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Timestamp</th>
                <th className="px-3 py-2 font-medium"><span className="inline-flex items-center gap-1">Src <InfoTip k="source" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium text-right"><span className="inline-flex items-center gap-1">Week <InfoTip k="week" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium text-right"><span className="inline-flex items-center gap-1">f_peak (Hz) <InfoTip k="fPeak" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium text-right"><span className="inline-flex items-center gap-1">TSI % <InfoTip k="tsi" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium text-right"><span className="inline-flex items-center gap-1">ζ <InfoTip k="zeta" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium text-right"><span className="inline-flex items-center gap-1">SNR (dB) <InfoTip k="snr" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium text-right"><span className="inline-flex items-center gap-1">Jitter ±% <InfoTip k="jitter" side="bottom" /></span></th>
                <th className="px-3 py-2 font-medium"><span className="inline-flex items-center gap-1">Verdict <InfoTip k="predictedLabel" side="bottom" /></span></th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {scans.map((s) => {
                const hot = s.id === highlightScanId;
                const color = lightColor(s.trafficLight);
                return (
                  <tr
                    key={s.id}
                    className="border-b border-line/50 transition-colors hover:bg-bg-card"
                    style={hot ? { background: "rgba(0,255,170,0.06)" } : undefined}
                  >
                    <td className="px-3 py-2 text-text-faint">{s.id}</td>
                    <td className="px-3 py-2 text-text-muted whitespace-nowrap">
                      {fmtTs(s.createdAt)}
                    </td>
                    <td className="px-3 py-2">{sourceBadge(s.source)}</td>
                    <td className="px-3 py-2 text-right text-text-muted">{fmt(s.week, 1)}</td>
                    <td className="px-3 py-2 text-right text-text">{fmt(s.fPeakHz, 1)}</td>
                    <td className="px-3 py-2 text-right font-semibold" style={{ color }}>
                      {fmt(s.tsiPct, 1)}
                    </td>
                    <td className="px-3 py-2 text-right text-text-muted">{fmt(s.zeta, 4)}</td>
                    <td className="px-3 py-2 text-right text-text-muted">{fmt(s.snrDb, 1)}</td>
                    <td className="px-3 py-2 text-right text-text-muted">
                      {fmt(s.tsiStdNorm, 2)}
                    </td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
                        <span className="text-[11px] text-text-muted">{s.predictedLabel ?? "—"}</span>
                      </span>
                    </td>
                  </tr>
                );
              })}
              {scans.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-5 py-6 text-center text-[12px] text-text-faint">
                    No scans recorded yet — run a scan to populate the log.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Footer note */}
      {!loading && !error && scans.length > 0 && (
        <div className="border-t border-line px-5 py-2 text-[10px] text-text-faint">
          Every row is a persisted measurement. Values are raw output of the normalization
          pipeline (f_peak via Welch PSD + sub-bin interpolation; jitter = TSI σ after averaging).
        </div>
      )}
    </div>
  );
}
