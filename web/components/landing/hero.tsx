"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResonanceWaveBg } from "@/components/brand/resonance-wave-bg";

export function LandingHero() {
  return (
    <section className="relative flex min-h-[88vh] items-center justify-center overflow-hidden px-6 pt-24 md:pt-0">
      <ResonanceWaveBg />

      <div className="relative z-10 mx-auto flex max-w-3xl flex-col items-center text-center">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-bg-card/60 px-3 py-1.5 backdrop-blur">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent breathe" />
          <span className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            Resonant Modal Spectroscopy
          </span>
        </div>

        <h1 className="font-display text-[44px] font-semibold leading-[1.05] tracking-tight text-text md:text-[72px]">
          When can I <span className="text-accent">walk again?</span>
        </h1>

        <p className="mt-6 max-w-[600px] text-[15px] leading-relaxed text-text-muted md:text-[17px]">
          ResoScan listens to a fractured bone and tells the surgeon what an X-ray cannot:
          the exact day a patient can safely bear weight again — in 20 seconds,
          without radiation, with a device that costs less than dinner for two.
        </p>

        <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
          <Link href="/dashboard/scan">
            <Button variant="primary" size="xl" className="gap-2">
              Open the Clinical Dashboard
              <ArrowRight size={16} strokeWidth={2.2} />
            </Button>
          </Link>
          <a href="#how">
            <Button variant="outline" size="xl">See how it works</Button>
          </a>
        </div>

        {/* mini stat strip */}
        <div className="mt-12 grid grid-cols-3 gap-8 border-t border-line pt-5 md:gap-16">
          <Stat value="95%" label="AI accuracy" />
          <Stat value="₹8 000" label="Bill of materials" />
          <Stat value="100×" label="Cheaper than alternatives" />
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <div className="font-mono text-xl font-semibold text-text md:text-2xl">{value}</div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-faint">
        {label}
      </div>
    </div>
  );
}
