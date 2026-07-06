"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Activity, TrendingUp, Sparkles, Layers, FileText, HeartPulse, Share2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface TabDef {
  key: string;
  label: string;
  icon: React.ElementType;
  requiresScan?: boolean;  // greyed if no scan yet
}

const TABS: TabDef[] = [
  { key: "scan",          label: "Scan",           icon: Activity   },
  { key: "normalization", label: "Normalization",  icon: Layers,      requiresScan: true },
  { key: "status",        label: "Status",         icon: HeartPulse,  requiresScan: true },
  { key: "graph",         label: "Knowledge Graph", icon: Share2,     requiresScan: true },
  { key: "report",        label: "Report",         icon: FileText,    requiresScan: true },
  { key: "trend",         label: "Trend",          icon: TrendingUp   },
  { key: "model",         label: "Model",          icon: Sparkles     },
];

// All tabs are fully built now.
const AVAILABLE = new Set(["scan", "normalization", "status", "graph", "report", "trend", "model"]);

interface Props {
  rightSlot?: React.ReactNode;
  hasScan?: boolean;
}

export function SubviewTabs({ rightSlot, hasScan }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const activeView = params.get("view") ?? "scan";

  function switchView(key: string) {
    const sp = new URLSearchParams(params.toString());
    sp.set("view", key);
    router.replace(`/dashboard?${sp.toString()}`, { scroll: false });
  }

  return (
    <div className="flex items-center gap-0 border-b border-line px-5">
      {TABS.map(({ key, label, icon: Icon, requiresScan }) => {
        const built = AVAILABLE.has(key);
        const blocked = requiresScan && !hasScan;
        const active = activeView === key;
        const disabled = !built || blocked;

        return (
          <button
            key={key}
            disabled={disabled}
            onClick={() => !disabled && switchView(key)}
            title={blocked ? "Run a scan first" : !built ? "Coming soon" : undefined}
            className={cn(
              "relative flex items-center gap-1.5 px-3.5 py-3 text-[12px] transition-colors",
              active ? "text-accent"
                : disabled ? "cursor-default text-text-faint opacity-40"
                : "text-text-muted hover:text-text",
            )}
          >
            <Icon size={13} strokeWidth={1.7} />
            {label}
            {!built && (
              <span className="ml-1 rounded text-[9px] px-1 py-0.5 bg-bg-panel text-text-faint uppercase tracking-wide">
                soon
              </span>
            )}
            {active && (
              <span className="absolute bottom-0 left-0 right-0 h-[2px] rounded-t-full bg-accent" />
            )}
          </button>
        );
      })}
      {rightSlot && <div className="ml-auto pr-1">{rightSlot}</div>}
    </div>
  );
}
