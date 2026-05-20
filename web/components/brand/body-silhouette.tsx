/**
 * Minimal anatomical silhouette. Front-view body in single-line style.
 * The tibia (right leg, viewer's right) glows cyan and breathes when
 * `active` is true.
 */
"use client";

export function BodySilhouette({
  width = 220,
  active = true,
}: { width?: number; active?: boolean }) {
  const h = (width / 220) * 360;
  return (
    <svg
      viewBox="0 0 220 360"
      width={width}
      height={h}
      fill="none"
      stroke="var(--text-faint)"
      strokeWidth={1.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-label="Body silhouette with selected tibia"
    >
      {/* head */}
      <ellipse cx="110" cy="32" rx="18" ry="22" />
      {/* neck */}
      <path d="M104 54 L104 64 M116 54 L116 64" />
      {/* torso */}
      <path d="M70 70 Q110 60 150 70 L156 170 Q110 188 64 170 Z" />
      {/* clavicle hint */}
      <path d="M84 76 L136 76" opacity="0.5" />
      {/* arms */}
      <path d="M70 78 L46 130 L52 200" />
      <path d="M150 78 L174 130 L168 200" />
      {/* hands */}
      <circle cx="52" cy="208" r="5" />
      <circle cx="168" cy="208" r="5" />
      {/* hip ridge */}
      <path d="M68 170 L152 170" opacity="0.4" />
      {/* upper legs (femur) */}
      <path d="M88 178 L82 250" />
      <path d="M132 178 L138 250" />
      {/* knees */}
      <circle cx="82" cy="252" r="5" />
      <circle cx="138" cy="252" r="5" />
      {/* tibia + fibula */}
      <path d="M82 258 L80 330" />
      <path d="M138 258 L140 330" stroke="var(--accent)" strokeWidth="2.4" className={active ? "breathe" : undefined} />
      {/* foot */}
      <path d="M76 332 L98 332" />
      <path d="M134 332 L156 332" stroke="var(--accent)" strokeWidth="2.4" className={active ? "breathe" : undefined} />
      {/* tibia label */}
      <text x="155" y="298" fill="var(--accent)" fontSize="10" fontFamily="var(--font-mono)" letterSpacing="0.05em">
        TIBIA
      </text>
      {/* selection ring */}
      <circle cx="140" cy="295" r="22" stroke="var(--accent)" strokeOpacity="0.4" fill="none" strokeWidth="1" className={active ? "breathe" : undefined} />
    </svg>
  );
}
