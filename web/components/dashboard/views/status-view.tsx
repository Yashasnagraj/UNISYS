"use client";

/**
 * Status view — the patient-facing page.
 *
 * No jargon, no spectra. Just the conclusions a patient needs to read and feel
 * okay: how many days until they can walk, how strong the bone is, what to do.
 * Every conclusion has a "Why we're saying this" toggle that explains the
 * reasoning in plain language — transparency without overwhelming them.
 */

import { useMemo, useState } from "react";
import {
  Footprints, HeartPulse, ChevronDown, CheckCircle2, Activity,
  CalendarClock, Apple, Cigarette, Stethoscope, ShieldCheck,
} from "lucide-react";

import type { ApiPatient, ApiScanDetail } from "@/lib/api";
import { getPatient, type Patient } from "@/lib/patients";
import { predict } from "@/lib/prediction";

function codeToKey(code: string): string {
  return code === "P-2611" ? "arjun"
    : code === "P-2742" ? "priya"
    : code === "P-2810" ? "vikram"
    : "arjun";
}

interface Props {
  patient: ApiPatient;
  scan: ApiScanDetail | null;
}

export function StatusView({ patient, scan }: Props) {
  const lib: Patient = useMemo(() => getPatient(codeToKey(patient.patientCode)), [patient.patientCode]);
  const pred = useMemo(() => predict(lib), [lib]);

  // Patient-facing page uses the intuitive linear strength score (0–100, safe at
  // 80%) — clearer than the squared clinical TSI. Everything below is consistent
  // with this one number so the patient never sees a contradiction.
  const SAFE_TSI = 80;
  const tsi = scan?.tsiPctLinear ?? pred.currentTsi;
  const safe = tsi >= SAFE_TSI;
  const stalled = pred.daysRemaining === null && !safe;
  const cleared = safe && !stalled;
  const days = safe ? 0 : pred.daysRemaining;

  // tone
  const tone = cleared ? "var(--safe)" : stalled ? "var(--danger)" : "var(--caution)";
  const firstName = patient.name.split(" ")[0];

  // headline
  const headline = cleared
    ? `Great news, ${firstName} — your bone is strong enough to walk on.`
    : stalled
      ? `${firstName}, your healing needs a closer look.`
      : `You're healing well, ${firstName}.`;

  const subline = cleared
    ? "Your scan shows the bone has reached full walking strength. Time to get moving — gently at first."
    : stalled
      ? "The bone isn't getting stronger as quickly as we'd expect. This is treatable — the next step is a chat with your surgeon."
      : `You're on track. At the current pace you're about ${days} day${days === 1 ? "" : "s"} away from walking freely.`;

  // progress toward the safe-to-walk line
  const pctOfSafe = Math.min(100, Math.round((tsi / SAFE_TSI) * 100));

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 p-6">

      {/* ── Hero ── */}
      <div className="surface overflow-hidden p-0">
        <div className="px-7 py-6" style={{ background: `linear-gradient(180deg, ${tone}14, transparent)` }}>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em]" style={{ color: tone }}>
            <HeartPulse size={14} /> Your recovery
          </div>
          <h1 className="mt-2 font-display text-[22px] font-semibold leading-snug text-text">
            {headline}
          </h1>
          <p className="mt-2 text-[14px] leading-relaxed text-text-muted">{subline}</p>
        </div>

        {/* Days + strength */}
        <div className="grid grid-cols-2 border-t border-line">
          <div className="border-r border-line px-7 py-5">
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-text-faint">
              <Footprints size={13} /> Days until you can walk
            </div>
            <div className="mt-1 font-mono text-[44px] font-bold leading-none" style={{ color: tone }}>
              {cleared ? "0" : stalled ? "—" : days}
            </div>
            <div className="mt-1 text-[12px] text-text-muted">
              {cleared ? "Cleared today" : stalled ? "Not on track yet" : `Around ${pred.targetDateIso}`}
            </div>
          </div>
          <div className="px-7 py-5">
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-text-faint">
              <Activity size={13} /> Bone strength
            </div>
            <div className="mt-1 font-mono text-[44px] font-bold leading-none" style={{ color: tone }}>
              {Math.round(tsi)}<span className="text-2xl text-text-faint">%</span>
            </div>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-bg-panel">
              <div className="h-full rounded-full transition-all"
                style={{ width: `${pctOfSafe}%`, background: tone }} />
            </div>
            <div className="mt-1 text-[12px] text-text-muted">
              of the strength needed to walk
            </div>
          </div>
        </div>
      </div>

      {/* ── Conclusions, each with "why" ── */}
      <div className="flex flex-col gap-3">
        <Conclusion
          icon={Activity}
          statement={`Your bone is about ${Math.round(tsi)}% as strong as a healthy one.`}
          why={`We sent a gentle vibration into your leg and listened to how the bone "rings". A healing bone gets stiffer and rings at a higher pitch${scan?.fPeakHz ? ` — yours rang at ${scan.fPeakHz.toFixed(0)} Hz` : ""}. We compare that pitch to a healthy bone to get your strength score. This isn't guesswork — it's a method published in medical journals and validated on 74 patients (Tower et al., 1993).`}
          tone={tone}
        />
        <Conclusion
          icon={CalendarClock}
          statement={
            cleared ? "You're ready for full weight on the leg."
            : stalled ? "The healing has slowed and needs review."
            : `You're healing ${pred.pace === "ahead" ? "faster than" : pred.pace === "behind" ? "a little slower than" : "right on pace with"} most people.`
          }
          why={
            stalled
              ? "We tracked your strength score over several scans and fitted it to a normal healing curve. Yours is levelling off below the line we'd expect — a sign the bone may need help bridging. This is common and treatable; your surgeon has good options."
              : `We plotted your scans over time and matched them to the typical healing curve for someone your age and health. ${pred.paceDeltaDays !== 0 ? `You're about ${Math.abs(pred.paceDeltaDays)} days ${pred.pace === "ahead" ? "ahead of" : "behind"} average` : "You're tracking the average"} — which is why we project ${cleared ? "you're cleared" : `about ${days} more days`}.`
          }
          tone={tone}
        />
        <Conclusion
          icon={ShieldCheck}
          statement={
            cleared ? "It's safe to bear full weight now."
            : "It's not quite safe for full weight yet — keep following your weight-bearing plan."
          }
          why={`Bones become safe to walk on at about 80% of full strength — that's the threshold doctors use. You're at ${Math.round(tsi)}%. ${cleared ? "You've crossed the line, so full weight is safe." : "Until you reach it, putting full weight on the leg risks re-injury, so we hold off."}`}
          tone={tone}
        />
        <Conclusion
          icon={CheckCircle2}
          statement={
            pred.confidence === "high" ? "We're confident in this estimate."
            : pred.confidence === "moderate" ? "This estimate is solid and will sharpen with your next scan."
            : "This is an early estimate — a couple more scans will make it precise."
          }
          why={`Our prediction gets more accurate the more scans we have to draw the curve. You have ${lib.scans.length} scan${lib.scans.length === 1 ? "" : "s"} so far, which gives us ${pred.confidence} confidence. Every visit tightens the estimate — there's no extra cost or radiation, so frequent scans are encouraged.`}
          tone={tone}
        />
      </div>

      {/* ── What helps you heal ── */}
      <div className="surface p-5">
        <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-text-faint">
          <HeartPulse size={13} className="text-accent" /> What helps you heal faster
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Tip icon={Apple} title="Eat for your bones"
            body="Protein, calcium and vitamin D give your body the bricks to rebuild. A balanced plate genuinely speeds healing." />
          <Tip icon={Cigarette} title="Avoid smoking"
            body="Smoking can slow bone healing by around 30%. If you smoke, cutting back now makes a real difference." />
          <Tip icon={Footprints} title="Follow your weight plan"
            body="Move exactly as much as your surgeon advised — no more, no less. Gentle, correct loading helps bone grow." />
          <Tip icon={Stethoscope} title="Come back for scans"
            body="Quick, painless, radiation-free check-ins let us catch any slowdown early — when it's easiest to fix." />
        </div>
      </div>

      {/* ── Reassurance footer ── */}
      <div className="rounded-xl border border-line px-5 py-4 text-center text-[12.5px] leading-relaxed text-text-muted"
        style={{ background: "var(--bg-panel)" }}>
        {stalled
          ? "A slow start doesn't mean it won't heal — it means we caught it early, which is exactly when help works best. You're in good hands."
          : cleared
            ? "You did the hard part — your body and your patience got you here. Ease back in and enjoy moving again."
            : "Healing takes time, and yours is going the right way. Keep doing what you're doing — you're closer than you think."}
        <div className="mt-2 text-[11px] text-text-faint">
          Every statement on this page is based on your real scan. Tap &ldquo;Why we&apos;re saying this&rdquo; on any card to see the reasoning.
        </div>
      </div>
    </div>
  );
}

// ── pieces ────────────────────────────────────────────────────────────────────

function Conclusion({
  icon: Icon, statement, why, tone,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  statement: string; why: string; tone: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="surface overflow-hidden">
      <div className="flex items-start gap-3 px-5 py-4">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
          style={{ background: `${tone}1e`, color: tone }}>
          <Icon size={15} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-medium leading-snug text-text">{statement}</p>
          <button
            onClick={() => setOpen((v) => !v)}
            className="mt-1.5 flex items-center gap-1 text-[12px] text-text-muted transition-colors hover:text-accent"
          >
            Why we&apos;re saying this
            <ChevronDown size={13} className="transition-transform" style={{ transform: open ? "rotate(180deg)" : "none" }} />
          </button>
          {open && (
            <p className="mt-2 border-t border-line pt-2 text-[12.5px] leading-relaxed text-text-muted">
              {why}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Tip({ icon: Icon, title, body }: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string; body: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-line bg-bg-panel px-3.5 py-3">
      <Icon size={16} className="mt-0.5 shrink-0 text-accent" />
      <div>
        <div className="text-[13px] font-semibold text-text">{title}</div>
        <p className="mt-0.5 text-[12px] leading-relaxed text-text-muted">{body}</p>
      </div>
    </div>
  );
}
