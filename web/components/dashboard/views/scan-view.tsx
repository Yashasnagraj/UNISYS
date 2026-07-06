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

const OUTCOME_LABELS = ["Stable", "Delayed Union", "Non-Union", "Implant Failure"] as const;

/** Human-in-the-loop: clinician agrees with or overrides the ML verdict. The
 *  confirmed label feeds the next model retrain (approved data only). */
function VerdictFeedback({ scanId, predicted }: { scanId: number; predicted: string | null }) {
  const [state, setState] = useState<"idle" | "overriding" | "sent">("idle");
  const [sentLabel, setSentLabel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function agree() {
    setBusy(true);
    try {
      await api.confirmScan(scanId, { agree: true });
      if (predicted) await api.recordOutcome(scanId, { trueLabel: predicted });
      setSentLabel(predicted);
      setState("sent");
    } finally { setBusy(false); }
  }

  async function override(label: string) {
    setBusy(true);
    try {
      await api.confirmScan(scanId, { agree: false, overrideLabel: label });
      await api.recordOutcome(scanId, { trueLabel: label });
      setSentLabel(label);
      setState("sent");
    } finally { setBusy(false); }
  }

  if (state === "sent") {
    return (
      <div className="mt-3 border-t border-line pt-2.5 text-[11px] text-text-muted">
        <span style={{ color: "var(--accent)" }}>✓ Recorded</span> — outcome
        &ldquo;{sentLabel}&rdquo; added to the training set for the next model update.
      </div>
    );
  }

  return (
    <div className="mt-3 border-t border-line pt-2.5">
      <div className="text-[10px] uppercase tracking-[0.14em] text-text-faint">Clinician review</div>
      {state === "idle" ? (
        <div className="mt-1.5 flex items-center gap-2">
          <button
            onClick={agree} disabled={busy}
            className="rounded-md border border-line px-2.5 py-1 text-[11px] text-text hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
          >
            ✓ Agree
          </button>
          <button
            onClick={() => setState("overriding")} disabled={busy}
            className="rounded-md border border-line px-2.5 py-1 text-[11px] text-text-muted hover:text-text transition-colors disabled:opacity-50"
          >
            Override…
          </button>
        </div>
      ) : (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          {OUTCOME_LABELS.map((l) => (
            <button
              key={l} onClick={() => override(l)} disabled={busy}
              className="rounded-md border border-line px-2 py-1 text-[10.5px] text-text-muted hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
            >
              {l}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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
  const [capturing, setCapturing] = useState(false);  // true for the whole device await
  const [shape, setShape] = useState<ScanShape>(() => offlineShape(patient.patientCode));
  const [latestScan, setLatestScan] = useState<ApiScanDetail | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanSource, setScanSource] = useState<"device" | "replay" | "sim" | "sim-fallback" | null>(null);
  const [captureSignal, setCaptureSignal] = useState(0);  // bumps the captures panel on each scan
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
    // Live scan → anchor the healing model to the real measured (week, TSI) so
    // days-to-walk reflects THIS reading. No scan yet → offline demo fixture.
    if (latestScan?.tsiPct != null) {
      return predict({
        scans: [{ week: latestScan.week, tsiPct: latestScan.tsiPct }],
        smoker: patient.smoker, diabetic: patient.diabetic, age: patient.age,
      });
    }
    const key = patient.patientCode === "P-2611" ? "arjun"
      : patient.patientCode === "P-2742" ? "priya" : "vikram";
    return predict(getPatient(key));
  }, [latestScan, patient]);

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
    setCaptureSignal((c) => c + 1);   // tell the captures panel to take a reading
    if (offline) return;

    // REAL capture only — NO silent simulation. A device request may be satisfied
    // by the backend replaying a real captured batch (source "replay"); we reflect
    // whatever source the API actually returns and never fabricate a live reading.
    // On failure we surface the real reason instead of quietly faking a scan.
    setCapturing(true);
    try {
      const result = await api.createScan({
        source: "device",
        patientId: patient.id,
        week: scanParams.week,
        nSweeps: 1,          // real firmware is ~28 s/sweep; one live capture
      });
      setScanSource((result?.source as typeof scanSource) ?? "device");
      if (result) {
        setLatestScan(result);
        onScanCreated?.(result.id, result);
      }
    } catch (e: unknown) {
      setScanError(e instanceof Error ? e.message : "Device unavailable");
      setScanSource(null);
    } finally {
      setCapturing(false);
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

      {/* Source badge — states exactly where the values came from, honestly. */}
      {latestScan && !offline && (() => {
        const src = latestScan.source;
        const isReal = src === "device";        // live hardware only
        const isReplay = src === "replay";       // real captured batch, replayed
        const label =
          isReal ? `Live device · ADXL345 · scan #${latestScan.id}`
          : isReplay ? `Captured data · replayed through pipeline · scan #${latestScan.id}`
          : `Simulation · scan #${latestScan.id} · live hardware unavailable`;
        return (
          <div className="flex items-center gap-1.5 text-[11px]"
            style={{ color: isReal || isReplay ? "var(--accent)" : "var(--caution)" }}>
            {isReal ? <Wifi size={11} /> : <WifiOff size={11} />}
            {label}
            {" "}· values normalized by pipeline
          </div>
        );
      })()}
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

      {/* Device captures — real for Yashas, simulated for Priya/Vikram.
          Appends a new reading ~5s after each Run scan. */}
      {hasRealCaptures(patient.patientCode) && (
        <RealCapturesPanel patientCode={patient.patientCode} scanSignal={captureSignal} />
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

          <Button variant="primary" size="lg" className="w-full" onClick={runScan} disabled={scanning || capturing}>
            {capturing ? (
              <>
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                Capturing from device…
              </>
            ) : scanning ? (
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
              <button onClick={runScan} disabled={scanning || capturing}
                className="flex items-center gap-1.5 text-[12px] text-text-muted hover:text-accent transition-colors disabled:opacity-50">
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
            {latestScan && !offline && (
              <VerdictFeedback scanId={latestScan.id} predicted={latestScan.predictedLabel} />
            )}
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
