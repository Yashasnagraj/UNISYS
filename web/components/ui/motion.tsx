"use client";

/**
 * Shared motion language. Uses framer-motion (already a dependency) with the
 * SAME ease-out-cubic timing as AnimatedNumber, and respects the user's
 * reduced-motion preference (renders static when set).
 */

import { Children, isValidElement } from "react";
import { motion, useReducedMotion, type Transition } from "framer-motion";
import { cn } from "@/lib/utils";

const EASE = [0.33, 1, 0.68, 1] as const; // ease-out-cubic
const base = (delay = 0, duration = 0.45): Transition => ({ duration, ease: EASE, delay });

export function FadeIn({
  children, delay = 0, y = 8, className,
}: { children: React.ReactNode; delay?: number; y?: number; className?: string }) {
  const rm = useReducedMotion();
  if (rm) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={base(delay)}
    >
      {children}
    </motion.div>
  );
}

export function SlideUp({
  children, delay = 0, className,
}: { children: React.ReactNode; delay?: number; className?: string }) {
  return <FadeIn y={18} delay={delay} className={className}>{children}</FadeIn>;
}

/** Staggered reveal of its direct children. */
export function Stagger({
  children, className, gap = 0.06,
}: { children: React.ReactNode; className?: string; gap?: number }) {
  const rm = useReducedMotion();
  if (rm) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: gap } } }}
    >
      {Children.map(children, (child, i) =>
        isValidElement(child) ? (
          <motion.div
            key={i}
            variants={{
              hidden: { opacity: 0, y: 10 },
              show: { opacity: 1, y: 0, transition: base(0, 0.4) },
            }}
          >
            {child}
          </motion.div>
        ) : child,
      )}
    </motion.div>
  );
}

export { motion, EASE };
export const cnMotion = cn;
