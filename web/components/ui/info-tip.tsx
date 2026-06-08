"use client";

/**
 * InfoTip — a small "?" badge that reveals a plain-English explanation on hover
 * (desktop) or tap (touch). Pulls copy from lib/glossary.ts by key, or accepts
 * inline title/plain/why props.
 *
 * Usage:
 *   <InfoTip k="tsi" />                         // from glossary
 *   <InfoTip title="..." plain="..." why="..." />  // inline
 *
 * Pure CSS/JS, no portal — positioned absolutely with a high z-index. The
 * tooltip flips above by default and is width-capped so it never overflows.
 */

import { useState, useRef, useEffect } from "react";
import { HelpCircle } from "lucide-react";
import { lookup } from "@/lib/glossary";

interface Props {
  k?: string;            // glossary key
  title?: string;        // inline override
  plain?: string;
  why?: string;
  side?: "top" | "bottom";
  className?: string;
}

export function InfoTip({ k, title, plain, why, side = "top", className }: Props) {
  const entry = k ? lookup(k) : undefined;
  const heading = title ?? entry?.term ?? "";
  const body = plain ?? entry?.plain ?? "";
  const reason = why ?? entry?.why;

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  // Close on outside tap (touch devices)
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!heading && !body) return null;

  return (
    <span
      ref={ref}
      className={`relative inline-flex items-center ${className ?? ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label={`What is ${heading}?`}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="inline-flex items-center justify-center text-text-faint hover:text-accent transition-colors"
      >
        <HelpCircle size={12} strokeWidth={1.8} />
      </button>

      {open && (
        <span
          role="tooltip"
          className="absolute z-50 w-64 rounded-lg border border-line bg-bg-card p-3 text-left shadow-xl"
          style={{
            left: "50%",
            transform: "translateX(-50%)",
            ...(side === "top"
              ? { bottom: "calc(100% + 8px)" }
              : { top: "calc(100% + 8px)" }),
          }}
        >
          {heading && (
            <span className="mb-1 block font-display text-[12px] font-semibold text-text">
              {heading}
            </span>
          )}
          {body && (
            <span className="block text-[11.5px] leading-relaxed text-text-muted">
              {body}
            </span>
          )}
          {reason && (
            <span className="mt-1.5 block border-t border-line pt-1.5 text-[11px] leading-relaxed text-text-faint">
              {reason}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
