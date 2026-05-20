"use client";

import Link from "next/link";
import { ArrowRight, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LandingDemoCta() {
  return (
    <section className="border-y border-line bg-bg-panel px-6 py-24 md:px-12">
      <div className="mx-auto flex max-w-4xl flex-col items-center text-center">
        <Activity size={28} className="text-accent" strokeWidth={1.5} />
        <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-text md:text-5xl">
          See the device <span className="text-accent">in your hands.</span>
        </h2>
        <p className="mt-5 max-w-xl text-[14.5px] leading-relaxed text-text-muted md:text-base">
          The clinical console is the live demo. Walk through a real scan, swap between
          three patients, watch the AI predict the day each can walk.
        </p>
        <Link href="/dashboard/scan" className="mt-10">
          <Button variant="primary" size="xl" className="gap-2">
            Open the Clinical Dashboard
            <ArrowRight size={18} strokeWidth={2.2} />
          </Button>
        </Link>
      </div>
    </section>
  );
}
