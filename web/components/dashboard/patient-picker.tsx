"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { PATIENTS, statusColor } from "@/lib/patients";
import { cn } from "@/lib/utils";

export function PatientPicker() {
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const selected = params.get("p") ?? "arjun";
  const current = PATIENTS.find((p) => p.key === selected) ?? PATIENTS[0];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function choose(key: string) {
    const next = new URLSearchParams(params.toString());
    next.set("p", key);
    router.push(`${path}?${next.toString()}`);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="group flex items-center gap-3 rounded-full border border-line bg-bg-card pl-2 pr-4 py-1.5 hover:border-accent transition-colors"
      >
        <span
          className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold"
          style={{ background: statusColor(current.status), color: "#001619" }}
        >
          {current.name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
        </span>
        <span className="flex flex-col items-start leading-tight">
          <span className="text-[11px] uppercase tracking-wider text-text-faint">Patient</span>
          <span className="text-[13px] font-medium text-text">{current.name}</span>
        </span>
        <ChevronDown size={14} className="text-text-muted group-hover:text-accent transition-colors" />
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-[280px] overflow-hidden rounded-xl border border-line bg-bg-card shadow-2xl">
          {PATIENTS.map((p) => (
            <button
              key={p.key}
              onClick={() => choose(p.key)}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-bg-elevated transition-colors",
                p.key === current.key && "bg-bg-elevated"
              )}
            >
              <span
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold"
                style={{ background: statusColor(p.status), color: "#001619" }}
              >
                {p.name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
              </span>
              <div className="flex-1">
                <div className="text-[13px] font-medium text-text">{p.name}</div>
                <div className="text-[11px] text-text-faint">
                  {p.age} · {p.fractureType} · {p.bone}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
