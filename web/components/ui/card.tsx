"use client";

import { cn } from "@/lib/utils";

/** The universal surface card. `interactive` adds hover-lift; `glow` adds the
 *  accent halo used on hero surfaces. Token-driven — matches `.surface`. */
export function Card({
  className, interactive, glow, padded = true, ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  interactive?: boolean; glow?: boolean; padded?: boolean;
}) {
  return (
    <div
      className={cn(
        "surface",
        padded && "p-5",
        interactive && "card-interactive cursor-pointer",
        glow && "glow-accent",
        className,
      )}
      {...props}
    />
  );
}

/** Standard section heading: optional icon + title + subtitle + right slot. */
export function SectionHeader({
  icon: Icon, title, subtitle, right, className,
}: {
  icon?: React.ElementType; title: React.ReactNode; subtitle?: React.ReactNode;
  right?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <div className="flex items-start gap-2">
        {Icon && <Icon size={15} className="mt-0.5 text-accent" strokeWidth={1.7} />}
        <div>
          <div className="font-display text-[14.5px] font-semibold text-text leading-tight">{title}</div>
          {subtitle && <div className="mt-0.5 text-[11.5px] text-text-muted">{subtitle}</div>}
        </div>
      </div>
      {right}
    </div>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn("border-t border-line", className)} />;
}
