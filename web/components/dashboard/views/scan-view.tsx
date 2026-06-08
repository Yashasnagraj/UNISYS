"use client";

/**
 * Scan view — wraps the existing scan components, now fed from the API.
 *
 * Falls back to lib/scan.ts offline generation when:
 *   (a) ?demo=offline is set, or
 *   (b) the API call fails.
 *
 * On mount it runs a sim scan automatically so the view is never empty.
 */

import {
  Suspense, useEffect, useMemo, useRef, useState,
} from "react";
import { Play, RotateCcw, Activity, ChevronRight, Stethoscope, Microscope, Wifi, WifiOff } from "lucide-react";

import type { ApiPatient, ApiScanDetail } from "@/lib/api";
import { api } from "@/lib/api";
import { adaptApiScan } from "@/lib/adapt";
import {
  buildScan, paramsFromPatient, DEFAULT_PARAMS, type ScanParams, type ScanShape,
} from "@/lib/scan";
import { predict, predictionHeadline } from "@/lib/prediction";
import { generateClinicalSummary } from "@/lib/summary";
import { getPatient } from "@/lib/patients";

import { Button } from "@/components/ui/button";
import { BodySilhouette } from "@/components/brand/body-silhouette";
import { ResonanceGraph } from "@/components/dashboard/scan/resonance-graph";
import { WaveformStrip } from "@/components/dashboard/scan/waveform-strip";
import { SignalQuality } from "@/components/dashboard/scan/signal-quality";
import { AnimatedNumber } from "@/components/dashboard/scan/animated-number";
import { ClinicalMetricsGrid } from "@/components/dashboard/scan/clinical-metrics";
import { HealingTimeline } from "@/components/dashboard/scan/healing-timeline";
import { AiAssessment } from "@/components/dashboard/scan/ai-assessment";
import { Spectrogram } from "@/components/dashboard/scan/spectrogram";
import { ScanControls } from "@/components/dashboard/scan/scan-controls";
import { ScanHistoryTable } from "@/components/dashboard/scan-history-table";
import { RealCapturesPanel } from "@/components/dashboard/real-captures-panel";
import { hasRealCaptures } from "@/lib/real-captures";
import { InfoTip } from "@/components/ui/info-tip";

const SCAN_DURATION_MS = 2200;

// ── helpers ───────────────────────────────────────────────────────────────────

function offlineShape(patientCode: string, params?: Partial<ScanParams>): ScanShape {
  const p = getPatient(
    // map patient_code e.g. P-2611 → key arjun
    patientCode === "P-2611" ? "arjun"
    : patientCode === "P-2742" ? "priya"
    : patientCode === "P-2810" ? "vikram"
    : patientCode,
  );
  const base = paramsFromPatient(p);
  return buildScan({ ...base, ...params });
}

// ── props ─────────────────────────────────────────────────────────────────────

interface Props {
  patient: ApiPatient;
  /** Notify parent of new scanId + full scan so normalization/report views can use it */
  onScanCreated?: (id: number, scan: ApiScanDetail) => void;
  offline?: boolean;
}

// ── component ─────────────────────────────────────────────────────────────────

export function ScanView({ patient, onScanCreated, offline }: Props) {
  const [scanParams, setScanParams] = useState<ScanParams>(() =>
    offlineShape(patient.patientCode).metrics
      ? offlineShape(patient.patientCode, undefined)
        ? (() => {
            const p = getPatient(patient.patientCode === "P-2611" ? "arjun" : patient.patientCode === "P-2742" ? "priya" : "vikram");
            return paramsFromPatient(p);
          })()
        : DEFAULT_PARAMS
      : DEFAULT_PARAMS,
  );

  const [progress, setProgress] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [shape, setShape] = useState<ScanShape>(() => offlineShape(patient.patientCode));
  const [latestScan, setLatestScan] = useState<ApiScanDetail | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanSource, setScanSource] = useState<"device" | "sim" | "sim-fallback" | null>(null);
  const rafRef = useRef<number | null>(null);

  // Re-seed when patient changes
  useEffect(() => {
    setShape(offlineShape(patient.patientCode));
    setScanParams(
      (() => {
        const key = patient.patientCode === "P-2611" ? "arjun"
          : patient.patientCode === "P-2742" ? "priya" : "vikram";
        const p = getPatient(key);
        return paramsFromPatient(p);
      })(),
    );
    setLatestScan(null);
    setProgress(0);
    startAnimation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient.patientCode]);

  // derive display shape from latest API scan OR offline params
  const displayShape = useMemo(() => {
    if (latestScan) return adaptApiScan(latestScan);
    return buildScan(scanParams);
  }, [latestScan, scanParams]);

  const pred = useMemo(() => {
    const key = patient.patientCode === "P-2611" ? "arjun"
      : patient.patientCode === "P-2742" ? "priya" : "vikram";
    return predict(getPatient(key));
  }, [patient.patientCode]);

  const headline = predictionHeadline(pred);
  const week = latestScan?.week ?? scanParams.week;

  const summary = useMemo(() => generateClinicalSummary({
    bone: patient.bone,
    fractureType: patient.fractureType,
    week,
    m: displayShape.metrics,
    patientName: patient.name,
  }), [patient.bone, patient.fractureType, patient.name, week, displayShape.metrics]);

  function startAnimation() {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setScanning(true);
    setProgress(0);
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / SCAN_DURATION_MS);
      setProgress(t);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
      else setScanning(false);
    };
    rafRef.current = requestAnimationFrame(tick);
  }

  async function runScan() {
    setScanError(null);
    startAnimation();
    if (offline) return;

    // Try device first; fall back to sim if device is unavailable (503)
    let result: ApiScanDetail | null = null;
    try {
      result = await api.createScan({
        source: "device",
        patientId: patient.id,
        week: scanParams.week,
        nSweeps: 8,
      });
      setScanSource("device");
    } catch {
      // Device unavailable — run simulation through the real normalization pipeline
      try {
        result = await api.createScan({
          source: "sim",
          patientId: patient.id,
          week: scanParams.week,
          callusPct: scanParams.callusPct,
          nSweeps: 8,
        });
        setScanSource("sim-fallback");
      } catch (e: unknown) {
        setScanError(e instanceof Error ? e.message : "Scan failed");
        return;
      }
    }

    if (result) {
      setLatestScan(result);
      onScanCreated?.(result.id, result);
    }
  }

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }, []);

  const toneColor =
    displayShape.metrics.trafficLight === "green" ? "var(--safe)"
    : displayShape.metrics.trafficLight === "amber" ? "var(--caution)"
    : "var(--danger)";

  const numbersActive = progress > 0.55;
  const updateParams = (p: Partial<ScanParams>) =>
    setScanParams((prev) => ({ ...prev, ...p }));

  return (
    <div className="flex flex-col gap-6 p-6">

      {/* API source badge */}
      {/* Source badge — shows exactly where values came from */}
      {latestScan && !offline && (
        <div className="flex items-center gap-1.5 text-[11px]"
          style={{ color: scanSource === "device" ? "var(--accent)" : "var(--caution)" }}>
          {scanSource === "device" ? <Wifi size={11} /> : <WifiOff size={11} />}
          {scanSource === "device"
            ? `Device scan · scan #${latestScan.id} · real ADXL345 data`
            : `Simulation · scan #${latestScan.id} · device unavailable (CS pin — re-seat wiring)`}
          {" "}· values normalized by pipeline
        </div>
      )}
      {offline && (
        <div className="flex items-center gap-1.5 text-[11px] text-text-faint">
          <WifiOff size={11} /> Offline demo mode
        </div>
      )}
      {scanError && (
        <div className="text-[11px]" style={{ color: "var(--caution)" }}>
          {scanError}
        </div>
      )}

      {/* Device captures — real for Yashas, simulated for Priya/Vikram */}
      {hasRealCaptures(patient.patientCode) && (
        <RealCapturesPanel patientCode={patient.patientCode} />
      )}

      {/* TOP STRIP */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">

        {/* LEFT */}
        <aside className="flex flex-col gap-5">
          <div className="surface flex flex-col items-center gap-4 p-5">
            <BodySilhouette width={180} active={scanning} />
            <div className="w-full border-t border-line pt-3 text-center">
              <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">Region selected</div>
              <div className="font-display text-base font-semibold text-text">
                {patient.bone} · Mid-shaft
              </div>
              <div className="mt-0.5 text-[11px] text-text-muted">
                Pitch-catch · Medial malleolus → Tibial tuberosity
              </div>
            </div>
          </div>

          <div className="surface p-5">
            <div className="flex items-center gap-3">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full text-[14px] font-semibold"
                style={{ background: toneColor, color: "#001619" }}
              >
                {patient.name.split(" ").map((s) => s[0]).join("")}
              </div>
              <div className="leading-tight">
                <div className="font-display text-[15px] font-semibold text-text">{patient.name}</div>
                <div className="text-[11px] text-text-muted">
                  {patient.patientCode} · {patient.age} yr · {patient.sex}
                </div>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-[11px]">
              <div>
                <div className="text-text-faint uppercase tracking-wider">Fracture</div>
                <div className="text-text">{patient.fractureType}</div>
              </div>
              <div>
                <div className="text-text-faint uppercase tracking-wider">Week</div>
                <div className="font-mono text-text">{week.toFixed(1)}</div>
              </div>
              <div>
                <div className="text-text-faint uppercase tracking-wider">Smoker</div>
                <div className="text-text">{patient.smoker ? "Yes" : "No"}</div>
              </div>
              <div>
                <div className="text-text-faint uppercase tracking-wider">Diabetic</div>
                <div className="text-text">{patient.diabetic ? "Yes" : "No"}</div>
              </div>
            </div>
          </div>

          <Button variant="primary" size="lg" className="w-full" onClick={runScan} disabled={scanning}>
            {scanning ? (
              <>
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                Scanning…
              </>
            ) : (
              <>
                <Play size={16} strokeWidth={2} />
                Run scan
              </>
            )}
          </Button>
        </aside>

        {/* CENTER */}
        <div className="flex flex-col gap-5">
          <div className="surface min-h-[400px] p-6">
            <header className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity size={16} className="text-accent" strokeWidth={1.8} />
                <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
                  Frequency response (PSD) <InfoTip k="psd" side="bottom" />
                </span>
              </div>
              <span className="font-mono text-[11px] text-text-faint">
                {Math.round(progress * 4096)} / 4096 samples
              </span>
            </header>
            <ResonanceGraph shape={displayShape} progress={progress} />
          </div>

          <div className="surface p-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
                Time-domain waveform <InfoTip k="waveform" side="bottom" />
              </span>
              <SignalQuality progress={progress} score={displayShape.qualityScore} />
            </div>
            <WaveformStrip shape={displayShape} progress={progress} />
            <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
              <div className="font-mono text-[11px] text-text-faint">
                20–1100 Hz sweep
              </div>
              <button onClick={runScan} disabled={scanning}
                className="flex items-center gap-1.5 text-[12px] text-text-muted hover:text-accent transition-colors">
                <RotateCcw size={13} /> Re-scan
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <aside className="flex flex-col gap-4">
          <div className="surface p-5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] text-text-faint">
              Healing score <InfoTip k="healingScore" />
            </div>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="font-mono text-[52px] font-semibold leading-none" style={{ color: toneColor }}>
                <AnimatedNumber value={Math.round(displayShape.metrics.tsi)} active={numbersActive} />
              </span>
              <span className="font-mono text-2xl text-text-faint">%</span>
            </div>
            <div className="mt-1 text-[12px] text-text-muted">Bone stiffness vs healthy reference</div>
          </div>

          <div className="surface p-5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.18em] text-text-faint">
              Days to walk <InfoTip k="daysToWalk" />
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="font-mono text-[40px] font-semibold leading-none" style={{ color: toneColor }}>
                {pred.daysRemaining === null
                  ? "—"
                  : <AnimatedNumber value={pred.daysRemaining} active={numbersActive} />}
              </span>
              {pred.daysRemaining !== null && (
                <span className="font-mono text-base text-text-faint">days</span>
              )}
            </div>
            <div className="mt-1 text-[12px] text-text-muted">
              {pred.daysRemaining === null
                ? "AI projects healing has stalled — escalate to surgeon."
                : pred.daysRemaining === 0
                  ? "Cleared today for full weight-bearing."
                  : `Projected clearance: ${pred.targetDateIso}`}
            </div>
          </div>

          <div className="surface p-5" style={{ borderLeft: `3px solid ${toneColor}` }}>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em]" style={{ color: toneColor }}>
              {displayShape.metrics.trafficLight === "green" ? "Cleared"
               : displayShape.metrics.trafficLight === "amber" ? "Caution" : "Risk"}
            </span>
            <h3 className="mt-1 font-display text-[15px] font-semibold text-text">
              {displayShape.metrics.classification === "Stable"
                ? "Safe for full weight-bearing"
                : displayShape.metrics.classification === "Delayed Union"
                  ? "Partial weight-bearing advised"
                  : displayShape.metrics.classification === "Implant Failure"
                    ? "Loose hardware detected"
                    : "Refer to orthopaedic surgeon"}
            </h3>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-muted">
              {displayShape.metrics.recommendation}
            </p>
          </div>
        </aside>
      </section>

      {/* DEEPER SECTION */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <ScanControls params={scanParams} onChange={updateParams} />
        <div className="surface p-5">
          <header className="mb-1 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Microscope size={14} className="text-accent" strokeWidth={1.6} />
              <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
                Healing timeline · 16 weeks
              </span>
            </div>
            <span className="font-mono text-[11px] text-text-faint">
              week {week} · TSI {displayShape.metrics.tsi.toFixed(0)}%
            </span>
          </header>
          <HealingTimeline currentWeek={week} currentTsi={displayShape.metrics.tsi} />
        </div>
        <AiAssessment shape={displayShape} />
      </section>

      {/* METRICS */}
      <section className="flex flex-col gap-4">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Stethoscope size={15} className="text-accent" strokeWidth={1.6} />
            <h2 className="flex items-center gap-1.5 font-display text-base font-semibold text-text">
              Clinical metrics <InfoTip k="rust" side="bottom" />
            </h2>
          </div>
        </header>
        <ClinicalMetricsGrid m={displayShape.metrics} />
      </section>

      {/* SPECTROGRAM + SUMMARY */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-text-faint">
              Spectrogram · frequency over time <InfoTip k="spectrogram" side="bottom" />
            </span>
          </div>
          <Spectrogram data={displayShape.spectrogram} />
          <p className="mt-3 border-t border-line pt-3 text-[12px] leading-relaxed text-text-muted">
            The vertical band lights up where the bone resonated strongest — signature changes as bone heals.
          </p>
        </div>
        <div className="surface p-5">
          <div className="mb-3 text-[11px] uppercase tracking-[0.16em] text-text-faint">
            Clinical summary
          </div>
          <p className="text-[13.5px] leading-relaxed text-text">{summary}</p>
        </div>
      </section>

      {/* MEASUREMENT LOG — real persisted scans with timestamps */}
      {!offline && (
        <section>
          <ScanHistoryTable
            patientCode={patient.patientCode}
            highlightScanId={latestScan?.id ?? null}
            refreshKey={latestScan?.id ?? 0}
          />
        </section>
      )}
    </div>
  );
}
