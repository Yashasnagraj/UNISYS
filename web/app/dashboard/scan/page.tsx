"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Play, RotateCcw, Activity, ChevronRight, Stethoscope, Microscope } from "lucide-react";

import { getPatient, latestScan } from "@/lib/patients";
import { predict, predictionHeadline } from "@/lib/prediction";
import {
  buildScan, paramsFromPatient, DEFAULT_PARAMS, type ScanParams,
} from "@/lib/scan";
import { generateClinicalSummary } from "@/lib/summary";

import { Button } from "@/components/ui/button";
import { BodySilhouette } from "@/components/brand/body-silhouette";
import { ResonanceGraph } from "@/components/dashboard/scan/resonance-graph";
import { WaveformStrip } from "@/components/dashboard/scan/waveform-strip";
import { SignalQuality } from "@/components/dashboard/scan/signal-quality";
import { AnimatedNumber } from "@/components/dashboard/scan/animated-number";
import { ScanControls } from "@/components/dashboard/scan/scan-controls";
import { ClinicalMetricsGrid } from "@/components/dashboard/scan/clinical-metrics";
import { HealingTimeline } from "@/components/dashboard/scan/healing-timeline";
import { Spectrogram } from "@/components/dashboard/scan/spectrogram";
import { AiAssessment } from "@/components/dashboard/scan/ai-assessment";

const SCAN_DURATION_MS = 2200;

export default function ScanPage() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted">Loading…</div>}>
      <ScanPageInner />
    </Suspense>
  );
}

function ScanPageInner() {
  const params = useSearchParams();
  const patient = getPatient(params.get("p") ?? "arjun");

  const [scanParams, setScanParams] = useState<ScanParams>(() => paramsFromPatient(patient));
  const [progress, setProgress] = useState(1);
  const [scanning, setScanning] = useState(false);
  const rafRef = useRef<number | null>(null);

  // Re-seed params when patient changes
  useEffect(() => {
    setScanParams(paramsFromPatient(patient));
    // restart scan animation
    setProgress(0);
    const t = setTimeout(startScan, 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient.key]);

  // Derive everything from scanParams
  const shape = useMemo(() => buildScan(scanParams), [scanParams]);
  const pred = useMemo(() => predict(patient), [patient]);  // days-to-walk stays patient-driven
  const headline = predictionHeadline(pred);
  const last = latestScan(patient);

  const summary = useMemo(() => generateClinicalSummary({
    bone: patient.bone,
    fractureType: patient.fractureType,
    week: scanParams.week,
    m: shape.metrics,
    patientName: patient.name,
  }), [patient.bone, patient.fractureType, patient.name, scanParams.week, shape.metrics]);

  function startScan() {
    if (scanning) return;
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

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }, []);

  // When sliders change, advance progress to 1 (already-scanned state)
  // but mark as freshly updated so counters animate
  const lastParamsRef = useRef<ScanParams>(scanParams);
  useEffect(() => {
    if (lastParamsRef.current !== scanParams) {
      lastParamsRef.current = scanParams;
      // gently re-animate counters by toggling
      setProgress(0.5);
      const id = setTimeout(() => setProgress(1), 80);
      return () => clearTimeout(id);
    }
  }, [scanParams]);

  const tone = headline.tone;
  const toneColor =
    shape.metrics.trafficLight === "green" ? "var(--safe)"
    : shape.metrics.trafficLight === "amber" ? "var(--caution)"
    : "var(--danger)";

  const updateParams = (p: Partial<ScanParams>) =>
    setScanParams((prev) => ({ ...prev, ...p }));

  const numbersActive = progress > 0.55;

  return (
    <div className="flex flex-col gap-6 p-6">

      {/* ============================ TOP STRIP ============================ */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">

        {/* LEFT */}
        <aside className="flex flex-col gap-5">
          <div className="surface flex flex-col items-center gap-4 p-5">
            <BodySilhouette width={180} active={scanning} />
            <div className="w-full border-t border-line pt-3 text-center">
              <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
                Region selected
              </div>
              <div className="font-display text-base font-semibold text-text">
                Right Tibia · Mid-shaft
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
                <div className="font-display text-[15px] font-semibold text-text">
                  {patient.name}
                </div>
                <div className="text-[11px] text-text-muted">
                  {patient.id} · {patient.age} yr · {patient.sex}
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
                <div className="font-mono text-text">{last.week.toFixed(1)}</div>
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

          <Button
            variant="primary"
            size="lg"
            className="w-full"
            onClick={startScan}
            disabled={scanning}
          >
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
                <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
                  Frequency response (PSD)
                </span>
              </div>
              <span className="font-mono text-[11px] text-text-faint">
                {Math.round(progress * 4096)} / 4096 samples
              </span>
            </header>
            <ResonanceGraph shape={shape} progress={progress} />
          </div>

          <div className="surface p-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
                Time-domain waveform
              </span>
              <SignalQuality progress={progress} score={shape.qualityScore} />
            </div>
            <WaveformStrip shape={shape} progress={progress} />
            <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
              <div className="font-mono text-[11px] text-text-faint">
                Scan #{patient.scans.length.toString().padStart(2,"0")} · 2.2 s · 20–1100 Hz sweep
              </div>
              <button
                onClick={startScan}
                disabled={scanning}
                className="flex items-center gap-1.5 text-[12px] text-text-muted hover:text-accent transition-colors"
              >
                <RotateCcw size={13} />
                Re-scan
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <aside className="flex flex-col gap-4">
          <div className="surface p-5">
            <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
              Healing score
            </div>
            <div className="mt-1 flex items-baseline gap-1">
              <span className="font-mono text-[52px] font-semibold leading-none" style={{ color: toneColor }}>
                <AnimatedNumber value={Math.round(shape.metrics.tsi)} active={numbersActive} />
              </span>
              <span className="font-mono text-2xl text-text-faint">%</span>
            </div>
            <div className="mt-1 text-[12px] text-text-muted">
              Bone stiffness vs healthy reference
            </div>
          </div>

          <div className="surface p-5">
            <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
              Days to walk
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

          <div
            className="surface p-5"
            style={{ borderLeft: `3px solid ${toneColor}` }}
          >
            <div className="flex items-center gap-2">
              <span
                className="font-mono text-[10px] uppercase tracking-[0.14em]"
                style={{ color: toneColor }}
              >
                {shape.metrics.trafficLight === "green" ? "Cleared"
                 : shape.metrics.trafficLight === "amber" ? "Caution"
                 : "Risk"}
              </span>
            </div>
            <h3 className="mt-1 font-display text-[15px] font-semibold text-text">
              {shape.metrics.classification === "Stable"
                ? "Safe for full weight-bearing"
                : shape.metrics.classification === "Delayed Union"
                  ? "Partial weight-bearing advised"
                  : shape.metrics.classification === "Implant Failure"
                    ? "Loose hardware detected"
                    : "Refer to orthopaedic surgeon"}
            </h3>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-muted">
              {shape.metrics.recommendation}
            </p>
          </div>

          <a
            href={`/dashboard/patients?p=${patient.key}`}
            className="group flex items-center justify-between rounded-xl border border-line bg-bg-card px-4 py-3 text-[13px] text-text-muted transition-colors hover:border-accent hover:text-text"
          >
            <span>See full healing trajectory</span>
            <ChevronRight size={16} className="transition-transform group-hover:translate-x-0.5" />
          </a>
        </aside>
      </section>

      {/* ============================ DEEPER SECTION ============================ */}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        {/* Scan controls — left column to match the top layout */}
        <ScanControls params={scanParams} onChange={updateParams} />

        {/* Healing timeline — center */}
        <div className="surface p-5">
          <header className="mb-1 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Microscope size={14} className="text-accent" strokeWidth={1.6} />
              <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
                Healing timeline · 16 weeks
              </span>
            </div>
            <span className="font-mono text-[11px] text-text-faint">
              week {scanParams.week} · TSI {shape.metrics.tsi.toFixed(0)}%
            </span>
          </header>
          <HealingTimeline currentWeek={scanParams.week} currentTsi={shape.metrics.tsi} />
        </div>

        {/* AI Assessment — right */}
        <AiAssessment shape={shape} />
      </section>

      {/* ============================ METRICS + EXTRAS ============================ */}

      <section className="flex flex-col gap-4">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Stethoscope size={15} className="text-accent" strokeWidth={1.6} />
            <h2 className="font-display text-base font-semibold text-text">
              Clinical metrics
            </h2>
          </div>
          <span className="font-mono text-[11px] text-text-faint">
            from this scan
          </span>
        </header>
        <ClinicalMetricsGrid m={shape.metrics} />
      </section>

      {/* ============================ SPECTROGRAM + SUMMARY ============================ */}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
              Spectrogram · frequency over time
            </span>
            <span className="font-mono text-[11px] text-text-faint">
              500 ms sweep
            </span>
          </div>
          <Spectrogram data={shape.spectrogram} />
          <p className="mt-3 border-t border-line pt-3 text-[12px] leading-relaxed text-text-muted">
            The vertical band lights up where the bone vibrated back the strongest — the
            resonance signature changes shape as the bone heals.
          </p>
        </div>

        <div className="surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
              Clinical summary
            </span>
            <span className="font-mono text-[11px] text-text-faint">
              auto-generated · ready for chart
            </span>
          </div>
          <p className="text-[13.5px] leading-relaxed text-text">
            {summary}
          </p>
        </div>
      </section>

      {/* ============================ BOTTOM PARAMS STRIP ============================ */}

      <div className="rounded-xl border border-line bg-bg-panel px-5 py-3 font-mono text-[12px] text-text-muted">
        <span className="text-text-faint">Scan:</span>{" "}
        {patient.bone} · {patient.fractureType} · Week {scanParams.week} ·
        Stiffness {scanParams.callusPct.toFixed(0)}% ·
        Pressure {scanParams.pressureN.toFixed(1)} N ·
        {scanParams.implantLoose ? " Loose implant" : " No implant"}
      </div>

    </div>
  );
}
