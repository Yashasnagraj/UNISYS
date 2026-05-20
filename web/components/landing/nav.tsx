"use client";

import Link from "next/link";
import { Wordmark } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";

export function LandingNav() {
  return (
    <header className="absolute inset-x-0 top-0 z-20 flex h-16 items-center justify-between px-6 md:px-10">
      <Link href="/" className="flex items-center gap-2.5">
        <Wordmark />
      </Link>
      <nav className="hidden items-center gap-7 text-[13px] text-text-muted md:flex">
        <a href="#how" className="hover:text-text transition-colors">How it works</a>
        <a href="#team" className="hover:text-text transition-colors">Team</a>
        <Link href="/dashboard/scan" className="text-text">
          <Button variant="outline" size="sm">Open Dashboard</Button>
        </Link>
      </nav>
      <div className="md:hidden">
        <Link href="/dashboard/scan">
          <Button variant="outline" size="sm">Demo</Button>
        </Link>
      </div>
    </header>
  );
}
