"use client";

import { usePathname } from "next/navigation";
import { Wordmark } from "@/components/brand/wordmark";
import { PatientPicker } from "./patient-picker";

function routeLabel(path: string): string {
  if (path.startsWith("/dashboard/scan")) return "Live Scan";
  if (path.startsWith("/dashboard/patients")) return "Patients";
  if (path.startsWith("/dashboard/model")) return "Model";
  return "Dashboard";
}

export function ShellTopbar() {
  const path = usePathname();
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-line bg-bg-panel px-6">
      <div className="flex items-center gap-5 md:hidden">
        <Wordmark />
      </div>
      <div className="hidden md:flex items-center gap-3">
        <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">
          ResoScan Clinical Console
        </span>
        <span className="h-3 w-px bg-line" />
        <span className="text-[13px] text-text-muted">{routeLabel(path ?? "")}</span>
      </div>
      <PatientPicker />
    </header>
  );
}
