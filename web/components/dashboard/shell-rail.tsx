"use client";

import { Activity, Users, Sparkles, Home } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Wordmark } from "@/components/brand/wordmark";

const ITEMS = [
  { href: "/dashboard/scan",     label: "Scan",     icon: Activity },
  { href: "/dashboard/patients", label: "Patients", icon: Users },
  { href: "/dashboard/model",    label: "Model",    icon: Sparkles },
];

export function ShellRail() {
  const path = usePathname();
  return (
    <aside className="hidden md:flex w-[72px] shrink-0 flex-col items-center gap-2 border-r border-line bg-bg-panel py-5">
      <Link href="/" aria-label="Back to ResoScan landing" className="mb-5">
        <Wordmark className="scale-90" />
      </Link>
      <nav className="flex flex-1 flex-col items-center gap-1">
        {ITEMS.map((item) => {
          const active = path?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-label={item.label}
              className={cn(
                "group relative flex h-11 w-11 items-center justify-center rounded-lg transition-colors",
                active ? "text-accent" : "text-text-muted hover:text-text"
              )}
            >
              {active && (
                <span className="absolute left-[-9px] top-2 bottom-2 w-[2px] rounded-full bg-accent" />
              )}
              <Icon size={20} strokeWidth={1.6} />
              <span className="pointer-events-none absolute left-[58px] z-10 whitespace-nowrap rounded-md border border-line bg-bg-card px-2 py-1 text-[11px] text-text opacity-0 group-hover:opacity-100 transition-opacity">
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>
      <Link
        href="/"
        aria-label="Back to landing"
        className="mt-auto flex h-10 w-10 items-center justify-center rounded-lg text-text-faint hover:text-text"
      >
        <Home size={18} strokeWidth={1.6} />
      </Link>
    </aside>
  );
}
