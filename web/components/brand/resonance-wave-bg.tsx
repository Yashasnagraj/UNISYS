/**
 * Slow-breathing resonance background — a wide damped sinusoid that drifts
 * across the hero section at a barely-noticeable pace. Opacity 8-12%.
 */
export function ResonanceWaveBg() {
  const w = 2400;     // wide enough to drift -50% and tile
  const h = 600;

  // Pre-compute a damped sinusoidal SVG path
  const points: string[] = [];
  const samples = 360;
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const x = t * w;
    const env = Math.exp(-3 * (1 - t));      // grows then plateaus
    const y =
      h / 2 +
      Math.sin(t * Math.PI * 14) * 70 * env +
      Math.sin(t * Math.PI * 5)  * 35 * env;
    points.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
  }
  const d = points.join(" ");

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-y-0 left-0 drift will-change-transform"
        style={{ width: `${w}px` }}
      >
        <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden>
          <defs>
            <linearGradient id="wave-stroke" x1="0" x2="1">
              <stop offset="0%"  stopColor="var(--accent)" stopOpacity="0" />
              <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.85" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={d} stroke="url(#wave-stroke)" strokeWidth="1.2" fill="none" />
        </svg>
      </div>
      {/* radial vignette to fade into the page */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 0%, var(--bg-primary) 78%)",
        }}
      />
    </div>
  );
}
