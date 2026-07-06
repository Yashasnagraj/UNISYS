"use client";

import { cn } from "@/lib/utils";

type Tone = "accent" | "safe" | "caution" | "danger" | "neutral";

const TONE: Record<Tone, { fg: string; bg: string }> = {
  accent:  { fg: "var(--accent)",  bg: "var(--accent-tint)" },
  safe:    { fg: "var(--safe)",    bg: "var(--safe-tint)" },
  caution: { fg: "var(--caution)", bg: "var(--caution-tint)" },
  danger:  { fg: "var(--danger)",  bg: "var(--danger-tint)" },
  neutral: { fg: "var(--text-muted)", bg: "rgba(255,255,255,0.06)" },
};

/** Coloured status pill. Use `tone` for semantic color. */
export function Badge({
  tone = "neutral", children, className, dot,
}: { tone?: Tone; children: React.ReactNode; className?: string; dot?: boolean }) {
  const c = TONE[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide",
        className,
      )}
      style={{ color: c.fg, background: c.bg }}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: c.fg }} />}
      {children}
    </span>
  );
}

/** Quiet chip for tags/keywords (no semantic tone). */
export function Tag({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn(
      "inline-flex items-center rounded-md bg-bg-panel px-1.5 py-0.5 text-[9.5px] uppercase tracking-wide text-text-faint",
      className,
    )}>
      {children}
    </span>
  );
}
