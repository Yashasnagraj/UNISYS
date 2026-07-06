"use client";

/**
 * Knowledge Graph view — the reasoning layer, now interactive.
 *
 * Click any node → it focuses: its edges + neighbours light up, everything else
 * dims, and a detail panel slides in. Hover to preview, drag to pan, wheel to
 * zoom. The causal explanation and similar-case list cross-link into the graph.
 * All data is the existing api.patientGraph/similar/causal — no backend change.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Share2, GitBranch, Users, User, Activity, Bone, Zap, AlertTriangle,
  Flag, Maximize2, X, ArrowRight,
} from "lucide-react";
import { motion } from "framer-motion";

import type {
  ApiCausalExplanation, ApiEgoGraph, ApiGraphNode, ApiGraphEdge,
  ApiPatient, ApiSimilarCase,
} from "@/lib/api";
import { api } from "@/lib/api";
import { Card, SectionHeader } from "@/components/ui/card";
import { Badge, Tag } from "@/components/ui/badge";
import { FadeIn } from "@/components/ui/motion";
import { cn } from "@/lib/utils";

interface Props { patient: ApiPatient; scanId: number | null }

// ── palettes ─────────────────────────────────────────────────────────────────

function labelColor(label: string | null | undefined): string {
  if (label === "Stable") return "var(--safe)";
  if (label === "Delayed Union") return "var(--caution)";
  if (label === "Non-Union" || label === "Implant Failure") return "var(--danger)";
  return "var(--text-muted)";
}
function lightColor(tl: unknown): string {
  if (tl === "green") return "var(--safe)";
  if (tl === "amber") return "var(--caution)";
  if (tl === "red") return "var(--danger)";
  return "var(--accent)";
}
const NODE_ICON: Record<string, React.ElementType> = {
  patient: User, scan: Activity, bone: Bone, fracture: Zap,
  comorbidity: AlertTriangle, outcome: Flag,
};
const NODE_TYPE_LABEL: Record<string, string> = {
  patient: "Patient", scan: "Scan", bone: "Bone", fracture: "Fracture",
  comorbidity: "Comorbidity", outcome: "Outcome",
};
const EDGE_META: Record<string, { label: string; color: string; dash?: string }> = {
  has_scan:          { label: "has scan",      color: "var(--line)" },
  progressed_to:     { label: "progressed to", color: "var(--accent-deep)" },
  confirmed_outcome: { label: "outcome",       color: "var(--safe)" },
  of_bone:           { label: "of bone",       color: "var(--line-soft)" },
  has_fracture:      { label: "fracture",      color: "var(--line-soft)" },
  has_comorbidity:   { label: "comorbidity",   color: "var(--caution)" },
  similar_to:        { label: "similar to",    color: "var(--accent)", dash: "5 4" },
};

function nodeColor(n: ApiGraphNode, rootId: string): string {
  if (n.id === rootId) return "var(--accent)";
  switch (n.type) {
    case "patient": return "var(--accent-deep)";
    case "scan": return lightColor((n as Record<string, unknown>).traffic_light);
    case "comorbidity": return "var(--caution)";
    case "outcome": return labelColor(String(n.label ?? ""));
    default: return "var(--text-muted)";
  }
}

// ── deterministic sector layout ──────────────────────────────────────────────

interface Placed { node: ApiGraphNode; x: number; y: number; r: number }

function layout(ego: ApiEgoGraph, W: number, H: number): Record<string, Placed> {
  const rootId = `patient:${ego.patientId}`;
  const cx = W / 2, cy = H / 2;
  const ownScan = new Set<string>();
  ego.edges.forEach((e) => { if (e.type === "has_scan" && e.source === rootId) ownScan.add(e.target); });

  const groups: Record<string, ApiGraphNode[]> = { scan: [], context: [], outcome: [], foreign: [] };
  for (const n of ego.nodes) {
    if (n.id === rootId) continue;
    if (n.type === "scan") (ownScan.has(n.id) ? groups.scan : groups.foreign).push(n);
    else if (n.type === "patient") groups.foreign.push(n);
    else if (n.type === "outcome") groups.outcome.push(n);
    else groups.context.push(n);
  }
  // A patient can have dozens of scans — a readable graph shows only the most
  // recent few (by scan id). Cap own-scans and foreign nodes.
  const idNum = (n: ApiGraphNode) => parseInt(String(n.id).split(":")[1] || "0", 10);
  groups.scan.sort((a, b) => idNum(a) - idNum(b));
  if (groups.scan.length > 7) groups.scan = groups.scan.slice(-7);
  groups.foreign = groups.foreign.slice(0, 6);

  const out: Record<string, Placed> = {
    [rootId]: { node: ego.nodes.find((n) => n.id === rootId)!, x: cx, y: cy, r: 26 },
  };
  const place = (list: ApiGraphNode[], base: number, spread: number, radius: number, r: number) => {
    const m = list.length;
    list.forEach((node, j) => {
      const a = base + (m > 1 ? (j - (m - 1) / 2) * (spread / (m - 1)) : 0);
      out[node.id] = { node, x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a), r };
    });
  };
  const D = Math.PI / 180;
  place(groups.scan,    -90 * D, 155 * D, 150, 16);  // top arc (recent scans)
  place(groups.context, 175 * D,  70 * D, 128, 12);  // left arc
  place(groups.outcome,   5 * D,  55 * D, 132, 13);  // right arc
  place(groups.foreign,  90 * D, 118 * D, 188, 14);  // bottom, outer ring
  return out;
}

// ── main view ────────────────────────────────────────────────────────────────

export function KnowledgeGraphView({ patient, scanId }: Props) {
  const [causal, setCausal] = useState<ApiCausalExplanation | null>(null);
  const [similar, setSimilar] = useState<ApiSimilarCase[]>([]);
  const [ego, setEgo] = useState<ApiEgoGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    if (scanId == null) return;
    let live = true;
    setLoading(true); setSelected(null);
    Promise.all([api.causal(scanId), api.similar(scanId, 5), api.patientGraph(patient.id)])
      .then(([c, s, g]) => { if (!live) return; setCausal(c); setSimilar(s.cases); setEgo(g); setError(null); })
      .catch((e) => live && setError(e instanceof Error ? e.message : "Failed to load graph"))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [scanId, patient.id]);

  if (scanId == null)
    return <Empty>Run a scan first to see the reasoning graph.</Empty>;
  if (loading)
    return <Empty pulse>Building knowledge graph…</Empty>;
  if (error)
    return <div className="flex h-64 items-center justify-center text-[13px]" style={{ color: "var(--danger)" }}>{error}</div>;

  const rootId = ego ? `patient:${ego.patientId}` : "";
  const selectedNode = ego?.nodes.find((n) => n.id === selected) ?? null;

  return (
    <FadeIn className="flex flex-col gap-5 p-6">
      <header>
        <div className="flex items-center gap-2">
          <Share2 size={16} className="text-accent" strokeWidth={1.8} />
          <h2 className="font-display text-base font-semibold text-text">Knowledge Graph &amp; Causal Reasoning</h2>
        </div>
        <p className="mt-0.5 text-[12px] text-text-muted">
          Click any node to expand its connections. Hover to preview, drag to pan, scroll to zoom.
        </p>
      </header>

      {/* Causal narrative */}
      {causal && (
        <Card className="border-0 px-5 py-4" glow
          style={{ background: "var(--accent-tint-2)" }}>
          <div className="flex items-center gap-2">
            <GitBranch size={13} className="text-accent" />
            <span className="text-[11px] uppercase tracking-[0.16em] text-text-faint">Causal explanation</span>
          </div>
          <p className="mt-2 text-[14px] leading-relaxed text-text">{causal.narrative}</p>
          {causal.activeFactors.length > 0 && (
            <div className="mt-3 flex flex-col gap-1.5">
              {causal.activeFactors.map((f) => (
                <button key={f.factor}
                  onClick={() => setSelected(`comorb:${f.factor.includes("smoker") ? "smoker" : f.factor.includes("diabet") ? "diabetic" : f.factor}`)}
                  onMouseEnter={() => setHovered(`comorb:${f.factor.includes("smoker") ? "smoker" : f.factor.includes("diabet") ? "diabetic" : f.factor}`)}
                  onMouseLeave={() => setHovered(null)}
                  className="flex items-start gap-2 rounded-md px-1 py-0.5 text-left text-[12px] hover:bg-bg-elevated transition-colors">
                  <Badge tone={f.sign < 0 ? "danger" : "safe"} className="mt-0.5 shrink-0 font-mono normal-case">
                    {f.sign < 0 ? "↓ slows" : "↑ speeds"} · w{f.weight.toFixed(2)}
                  </Badge>
                  <div>
                    <span className="font-semibold text-text">{f.factor.replace(/_/g, " ")}</span>
                    <span className="text-text-muted"> — {f.value}</span>
                    <span className="block text-[10.5px] text-text-faint">{f.citation}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Graph + side panel */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card padded={false} className="relative overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-4">
            <SectionHeader icon={Share2} title="Patient graph"
              subtitle={selectedNode ? "Focused — click empty space to reset" : "Click a node to focus"} />
          </div>
          {ego && (
            <GraphCanvas ego={ego} rootId={rootId} rootLabel={patient.name}
              selected={selected} hovered={hovered}
              onSelect={setSelected} onHover={setHovered} />
          )}
          {ego && <Legend />}
        </Card>

        {/* Right: node detail OR similar cases */}
        {selectedNode ? (
          <NodeDetail node={selectedNode} rootId={rootId} ego={ego!} causal={causal}
            onClose={() => setSelected(null)} onGoto={setSelected} />
        ) : (
          <SimilarPanel similar={similar} onHover={(id) => setHovered(id)} onSelect={setSelected} />
        )}
      </div>
    </FadeIn>
  );
}

// ── the interactive canvas ───────────────────────────────────────────────────

function GraphCanvas({
  ego, rootId, rootLabel, selected, hovered, onSelect, onHover,
}: {
  ego: ApiEgoGraph; rootId: string; rootLabel: string;
  selected: string | null; hovered: string | null;
  onSelect: (id: string | null) => void; onHover: (id: string | null) => void;
}) {
  const W = 620, H = 448;
  const placed = useMemo(() => layout(ego, W, H), [ego]);
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    ego.nodes.forEach((n) => m.set(n.id, new Set()));
    ego.edges.forEach((e) => { m.get(e.source)?.add(e.target); m.get(e.target)?.add(e.source); });
    return m;
  }, [ego]);

  const active = selected ?? hovered;
  const focusSet = useMemo(() => {
    if (!active) return null;
    const s = new Set<string>([active]);
    neighbors.get(active)?.forEach((id) => s.add(id));
    return s;
  }, [active, neighbors]);

  // zoom / pan
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const onWheel = (e: React.WheelEvent) => {
    const k = Math.min(3, Math.max(0.55, view.k * (e.deltaY < 0 ? 1.12 : 0.89)));
    setView((v) => ({ ...v, k }));
  };
  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, ox: view.x, oy: view.y };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    setView((v) => ({ ...v, x: drag.current!.ox + (e.clientX - drag.current!.x), y: drag.current!.oy + (e.clientY - drag.current!.y) }));
  };
  const endDrag = () => { drag.current = null; };

  const edgeState = (e: ApiGraphEdge) => {
    if (!focusSet) return { on: true, dim: false };
    const on = e.source === active || e.target === active;
    return { on, dim: !on };
  };

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full select-none" style={{ maxHeight: 470, cursor: drag.current ? "grabbing" : "grab" }}
        onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
        onPointerUp={endDrag} onPointerLeave={endDrag}>
        <defs>
          {Object.entries(EDGE_META).map(([k, m]) => (
            <marker key={k} id={`arrow-${k}`} viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill={m.color} />
            </marker>
          ))}
        </defs>

        {/* click-catcher to clear selection */}
        <rect x={0} y={0} width={W} height={H} fill="transparent" onClick={() => onSelect(null)} />

        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`} style={{ transformOrigin: "center" }}>
          {/* edges */}
          {ego.edges.map((e, i) => {
            const a = placed[e.source], b = placed[e.target];
            if (!a || !b) return null;
            const meta = EDGE_META[e.type] ?? { label: e.type, color: "var(--line)" };
            const { on, dim } = edgeState(e);
            const highlighted = focusSet && on;
            return (
              <g key={i}>
                <motion.line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={meta.color} strokeDasharray={meta.dash}
                  markerEnd={`url(#arrow-${e.type})`}
                  initial={false}
                  animate={{
                    strokeWidth: highlighted ? 2.2 : 1.2,
                    opacity: dim ? 0.06 : highlighted ? 0.95 : (e.type === "similar_to" ? 0.55 : 0.4),
                  }}
                  transition={{ duration: 0.25 }}
                />
                {highlighted && e.type === "similar_to" && typeof (e as Record<string, unknown>).score === "number" && (
                  <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} textAnchor="middle"
                    fontSize={8} className="font-mono" fill="var(--accent)">
                    {Math.round(((e as Record<string, unknown>).score as number) * 100)}%
                  </text>
                )}
              </g>
            );
          })}

          {/* nodes */}
          {Object.values(placed).map((p, idx) => {
            const n = p.node;
            const isRoot = n.id === rootId;
            const col = nodeColor(n, rootId);
            const isSel = selected === n.id;
            const dim = focusSet ? !focusSet.has(n.id) : false;
            const label = isRoot ? rootLabel
              : n.type === "scan" ? `#${parseInt(String(n.id).split(":")[1] || "0", 10)}`
              : String(n.label ?? NODE_TYPE_LABEL[n.type] ?? n.type);
            const scanTsi = n.type === "scan" ? (n as Record<string, unknown>).tsi as number | undefined : undefined;
            return (
              <motion.g key={n.id}
                initial={{ opacity: 0, scale: 0.4 }}
                animate={{ opacity: dim ? 0.18 : 1, scale: isSel ? 1.18 : 1 }}
                transition={{ delay: Math.min(idx * 0.025, 0.4), duration: 0.35 }}
                style={{ cursor: "pointer", transformOrigin: `${p.x}px ${p.y}px` }}
                onClick={(e) => { e.stopPropagation(); onSelect(isSel ? null : n.id); }}
                onPointerEnter={() => onHover(n.id)} onPointerLeave={() => onHover(null)}
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") onSelect(isSel ? null : n.id); }}
              >
                {(isSel || (focusSet && focusSet.has(n.id) && active === n.id)) && (
                  <circle cx={p.x} cy={p.y} r={p.r + 6} fill="none" stroke={col} strokeWidth={1.5} opacity={0.4} />
                )}
                <circle cx={p.x} cy={p.y} r={p.r}
                  fill={isRoot ? col : "var(--bg-card)"} stroke={col}
                  strokeWidth={isRoot ? 0 : 2} />
                {/* inner label: initials for patients, TSI for scans */}
                {isRoot ? (
                  <text x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
                    fontSize={11} fontWeight={700} fill="#00201a">
                    {label.split(" ").map((s) => s[0]).slice(0, 2).join("")}
                  </text>
                ) : n.type === "scan" && scanTsi != null ? (
                  <text x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
                    fontSize={9} fontWeight={700} className="font-mono" fill={col}>
                    {Math.round(scanTsi)}
                  </text>
                ) : n.type === "patient" ? (
                  <text x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
                    fontSize={9} fontWeight={700} fill={col}>
                    {label.split(" ").map((s) => s[0]).slice(0, 2).join("")}
                  </text>
                ) : null}
                {/* outer label */}
                <text x={p.x} y={p.y + p.r + 11} textAnchor="middle"
                  fontSize={8.5} fill={dim ? "var(--text-faint)" : "var(--text-muted)"}
                  fontWeight={isSel ? 600 : 400}>
                  {label.length > 16 ? label.slice(0, 15) + "…" : label}
                </text>
              </motion.g>
            );
          })}
        </g>
      </svg>

      {/* reset control */}
      <button onClick={() => setView({ x: 0, y: 0, k: 1 })}
        title="Reset view"
        className="absolute right-3 top-3 rounded-md border border-line bg-bg-panel/80 p-1.5 text-text-muted hover:text-accent hover:border-accent transition-colors">
        <Maximize2 size={13} />
      </button>
    </div>
  );
}

// ── legend ───────────────────────────────────────────────────────────────────

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line px-4 py-2.5">
      {(["patient", "scan", "comorbidity", "outcome"] as const).map((t) => {
        const Icon = NODE_ICON[t];
        const col = t === "patient" ? "var(--accent)" : t === "scan" ? "var(--accent)"
          : t === "comorbidity" ? "var(--caution)" : "var(--safe)";
        return (
          <span key={t} className="flex items-center gap-1.5 text-[10px] text-text-faint">
            <Icon size={11} style={{ color: col }} /> {NODE_TYPE_LABEL[t]}
          </span>
        );
      })}
      <span className="flex items-center gap-1.5 text-[10px] text-text-faint">
        <span className="inline-block h-0 w-4 border-t-2 border-dashed" style={{ borderColor: "var(--accent)" }} /> similar
      </span>
      <span className="flex items-center gap-1.5 text-[10px] text-text-faint">
        <span className="inline-block h-0 w-4 border-t-2" style={{ borderColor: "var(--accent-deep)" }} /> progressed
      </span>
    </div>
  );
}

// ── node detail panel ────────────────────────────────────────────────────────

function NodeDetail({
  node, rootId, ego, causal, onClose, onGoto,
}: {
  node: ApiGraphNode; rootId: string; ego: ApiEgoGraph;
  causal: ApiCausalExplanation | null;
  onClose: () => void; onGoto: (id: string) => void;
}) {
  const Icon = NODE_ICON[node.type] ?? Share2;
  const col = nodeColor(node, rootId);
  const rec = node as Record<string, unknown>;
  const conns = ego.edges
    .filter((e) => e.source === node.id || e.target === node.id)
    .map((e) => {
      const otherId = e.source === node.id ? e.target : e.source;
      const other = ego.nodes.find((n) => n.id === otherId);
      return { edge: e, other };
    })
    .filter((c) => c.other);

  const factor = node.type === "comorbidity"
    ? causal?.activeFactors.find((f) => f.factor.includes(String(node.label))) : null;

  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
      <Card className="flex flex-col gap-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full"
              style={{ background: "var(--accent-tint)", color: col }}>
              <Icon size={16} />
            </span>
            <div>
              <div className="font-display text-[14px] font-semibold text-text">{String(node.label ?? node.type)}</div>
              <div className="text-[11px] text-text-faint uppercase tracking-wide">{NODE_TYPE_LABEL[node.type] ?? node.type}</div>
            </div>
          </div>
          <button onClick={onClose} className="text-text-faint hover:text-text transition-colors"><X size={16} /></button>
        </div>

        {/* type-specific facts */}
        <div className="flex flex-wrap gap-2">
          {node.type === "scan" && (
            <>
              {rec.tsi != null && <Badge tone={rec.traffic_light === "green" ? "safe" : rec.traffic_light === "amber" ? "caution" : "danger"}>TSI {Math.round(rec.tsi as number)}%</Badge>}
              {rec.week != null && <Badge tone="neutral">week {String(rec.week)}</Badge>}
              {rec.traffic_light != null && <Badge tone={rec.traffic_light === "green" ? "safe" : rec.traffic_light === "amber" ? "caution" : "danger"} dot>{String(rec.traffic_light)}</Badge>}
            </>
          )}
          {node.type === "patient" && (
            <>
              {rec.code != null && <Badge tone="neutral">{String(rec.code)}</Badge>}
              {rec.status != null && <Badge tone={rec.status === "cleared" ? "safe" : rec.status === "delayed" ? "caution" : "danger"} dot>{String(rec.status)}</Badge>}
            </>
          )}
          {node.type === "outcome" && <Badge tone={node.label === "Stable" ? "safe" : node.label === "Delayed Union" ? "caution" : "danger"}>confirmed outcome</Badge>}
        </div>

        {factor && (
          <div className="rounded-lg border border-line px-3 py-2 text-[11.5px]" style={{ background: factor.sign < 0 ? "var(--danger-tint)" : "var(--safe-tint)" }}>
            <span className="font-semibold text-text">{factor.sign < 0 ? "Slows healing" : "Speeds healing"}</span>
            <span className="text-text-muted"> (weight {factor.weight.toFixed(2)})</span>
            <span className="block text-[10.5px] text-text-faint">{factor.citation}</span>
          </div>
        )}

        {/* connections — click to hop */}
        <div>
          <div className="mb-1.5 text-[10px] uppercase tracking-[0.16em] text-text-faint">
            Connections ({conns.length})
          </div>
          <div className="flex flex-col gap-1">
            {conns.map(({ edge, other }, i) => (
              <button key={i} onClick={() => other && onGoto(other.id)}
                className="flex items-center justify-between gap-2 rounded-md border border-line px-2.5 py-1.5 text-left hover:border-accent hover:bg-bg-elevated transition-colors">
                <span className="flex items-center gap-1.5 text-[11.5px] text-text">
                  <span className="text-text-faint">{EDGE_META[edge.type]?.label ?? edge.type}</span>
                  <ArrowRight size={11} className="text-text-faint" />
                  {String(other!.label ?? other!.type)}
                </span>
                <Tag>{NODE_TYPE_LABEL[other!.type] ?? other!.type}</Tag>
              </button>
            ))}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

// ── similar cases panel ──────────────────────────────────────────────────────

function SimilarPanel({
  similar, onHover, onSelect,
}: { similar: ApiSimilarCase[]; onHover: (id: string | null) => void; onSelect: (id: string) => void }) {
  return (
    <Card className="flex flex-col gap-3">
      <SectionHeader icon={Users} title="Similar prior cases"
        subtitle="Closest matches in the cohort" />
      {similar.length === 0 ? (
        <p className="text-[12px] text-text-faint">No comparable prior cases in the cohort yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {similar.map((c, i) => (
            <button key={`${c.scanId}-${i}`}
              onMouseEnter={() => onHover(`scan:${c.scanId}`)} onMouseLeave={() => onHover(null)}
              onClick={() => onSelect(`scan:${c.scanId}`)}
              className="card-interactive rounded-lg border border-line px-3 py-2.5 text-left">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[12px] text-text">{c.patientCode ?? `#${c.patientId}`} · wk {c.week}</span>
                <span className="font-mono text-[11px] text-accent">match {(c.score * 100).toFixed(0)}%</span>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[11px] text-text-muted">TSI {c.tsiPct != null ? Math.round(c.tsiPct) : "—"}%</span>
                {c.confirmedOutcome ? (
                  <Badge tone={c.confirmedOutcome === "Stable" ? "safe" : c.confirmedOutcome === "Delayed Union" ? "caution" : "danger"}>✓ {c.confirmedOutcome}</Badge>
                ) : (
                  <span className="text-[11px]" style={{ color: labelColor(c.predictedLabel) }}>{c.predictedLabel ?? "—"}</span>
                )}
                {c.comorbidities.map((m) => <Tag key={m}>{m}</Tag>)}
              </div>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── misc ─────────────────────────────────────────────────────────────────────

function Empty({ children, pulse }: { children: React.ReactNode; pulse?: boolean }) {
  return (
    <div className={cn("flex h-64 items-center justify-center text-[13px] text-text-faint", pulse && "animate-pulse text-text-muted")}>
      {children}
    </div>
  );
}
