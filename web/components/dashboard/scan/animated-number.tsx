"use client";

import { useEffect, useState } from "react";

/** Smoothly animates from 0 to `value` when `active` flips true. */
export function AnimatedNumber({
  value,
  active,
  duration = 600,
  decimals = 0,
  format = (v) => v.toFixed(decimals),
}: {
  value: number;
  active: boolean;
  duration?: number;
  decimals?: number;
  format?: (v: number) => string;
}) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!active) {
      setShown(0);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(eased * value);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, active, duration]);

  return <>{format(shown)}</>;
}
