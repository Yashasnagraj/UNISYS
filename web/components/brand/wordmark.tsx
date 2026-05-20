import { cn } from "@/lib/utils";

export function Wordmark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="relative inline-flex h-7 w-7 items-center justify-center">
        {/* concentric rings — a stylised resonance source */}
        <svg
          viewBox="0 0 28 28"
          className="absolute inset-0 h-full w-full"
          aria-hidden
        >
          <circle cx="14" cy="14" r="3.2" fill="var(--accent)" />
          <circle cx="14" cy="14" r="7"   fill="none" stroke="var(--accent)" strokeOpacity="0.55" strokeWidth="1" />
          <circle cx="14" cy="14" r="11"  fill="none" stroke="var(--accent)" strokeOpacity="0.25" strokeWidth="1" />
        </svg>
      </span>
      <span className="font-display text-[15px] font-semibold tracking-tight text-text">
        Reso<span className="text-accent">Scan</span>
      </span>
    </div>
  );
}
