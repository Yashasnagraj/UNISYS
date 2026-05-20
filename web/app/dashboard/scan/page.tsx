"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Play, RotateCcw, Activity, ChevronRight } from "lucide-react";

import { getPatient, latestScan } from "@/lib/patients";
import { predict, predictionHeadline } from "@/lib/prediction";
import { buildScanShape } from "@/lib/scan";
import { Button } from "@/components/ui/button";
import { BodySilhouette } from "@/components/brand/body-silhouette";
import { ResonanceGraph } from "@/components/dashboard/scan/resonance-graph";
import { WaveformStrip } from "@/components/dashboard/scan/waveform-strip";
import { SignalQuality } from "@/components/dashboard/scan/signal-quality";
import { AnimatedNumber } from "@/components/dashboard/scan/animated-number";

const SCAN_DURATION_MS = 2500;

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
  const shape = useMemo(() => buildScanShape(patient), [patient]);
  const pred = useMemo(() => predict(patient), [patient]);
  const headline = predictionHeadline(pred);
  const last = latestScan(patient);

  const [progress, setProgress] = useState(1); // start showing the final state
  const [scanning, setScanning] = useState(false);
  const rafRef = useRef<number | null>(null);

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

  // restart progress so animated counters re-run on patient switch
  useEffect(() => {
    setProgress(0);
    const t = setTimeout(startScan, 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient.key]);

  const numbersActive = progress > 0.78;
  const tone = headline.tone;
  const toneColor =
    tone === "safe" ? "var(--safe)" :
    tone === "caution" ? "var(--caution)" :
    "var(--danger)";

  return (
    <div className="grid h-full grid-cols-1 gap-6 p-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">

      {/* --------------- LEFT COLUMN --------------- */}
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
              Start scan
            </>
          )}
        </Button>
      </aside>

      {/* --------------- CENTER COLUMN --------------- */}
      <section className="flex flex-col gap-5">
        <div className="surface flex-1 min-h-[460px] p-6">
          <header className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-accent" strokeWidth={1.8} />
              <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
                Frequency response
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
            <div className="flex items-center gap-2">
              <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
                Time-domain waveform
              </span>
            </div>
            <SignalQuality progress={progress} score={shape.qualityScore} />
          </div>
          <WaveformStrip shape={shape} progress={progress} />
          <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
            <div className="font-mono text-[11px] text-text-faint">
              Scan #{(patient.scans.length).toString().padStart(2, "0")} · 2.5 s · 20–1100 Hz sweep
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
      </section>

      {/* --------------- RIGHT COLUMN --------------- */}
      <aside className="flex flex-col gap-4">
        <div className="surface p-5">
          <div className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
            Healing score
          </div>
          <div className="mt-1 flex items-baseline gap-1">
            <span
              className="font-mono text-[56px] font-semibold leading-none"
              style={{ color: toneColor }}
            >
              <AnimatedNumber value={Math.round(pred.currentTsi)} active={numbersActive} />
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
            <span
              className="font-mono text-[44px] font-semibold leading-none"
              style={{ color: toneColor }}
            >
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

        <div className="surface p-5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-[0.18em] text-text-faint">
              Confidence
            </span>
            <span className="font-mono text-[13px] text-text">
              <AnimatedNumber value={95} active={numbersActive} />% sure
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-[600ms]"
              style={{ width: numbersActive ? "95%" : "0%" }}
            />
          </div>
          <div className="mt-2 text-[11px] text-text-faint">
            Random-forest AI · {pred.confidence} confidence fit
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
              {tone === "safe" ? "Cleared" : tone === "caution" ? "Caution" : "Risk"}
            </span>
          </div>
          <h3 className="mt-1 font-display text-[15px] font-semibold text-text">
            {tone === "safe"
              ? "Safe for full weight-bearing"
              : tone === "caution"
                ? "Partial weight-bearing advised"
                : "Refer to orthopaedic surgeon"}
          </h3>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-muted">
            {headline.message}
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
    </div>
  );
}
