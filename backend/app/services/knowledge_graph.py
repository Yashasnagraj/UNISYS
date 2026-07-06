"""
ResoScan knowledge graph.

Builds an in-memory NetworkX graph from the relational rows (patients, scans,
comorbidities, outcomes) so a new scan can be reasoned about against the cohort:
retrieve the most similar prior cases and expose a patient ego-graph for the UI.

The graph is rebuilt per request — the cohort is tiny (a handful of patients,
dozens of scans), so this is trivially cheap and always reflects the latest DB
state. Nothing here learns; it is deterministic retrieval over stored features.
"""
from __future__ import annotations

import json
import math
from typing import Optional

import networkx as nx
from sqlmodel import Session, select

from app.db.models import Outcome, Patient, Scan

# ── Similarity model ─────────────────────────────────────────────────────────
# Weighted z-score distance over a discriminative subset of the 25 signal
# features. Weights emphasise the mechanically-meaningful bands (resonance,
# stiffness, damping) over incidental time-domain stats. Values are relative
# importances, not fitted parameters — they encode domain priors, matching the
# feature-importance ordering the ML model itself learned (f-slope/damping lead).
SIMILARITY_FEATURE_WEIGHTS: dict[str, float] = {
    "tsi": 2.0,                    # stiffness proxy — the headline biomarker
    "f_peak": 2.0,                 # resonant frequency
    "q_factor": 1.5,               # sharpness (union quality)
    "damping_ratio": 1.5,          # energy loss (soft callus)
    "half_power_bandwidth": 1.0,
    "spectral_flatness": 1.0,      # tonal vs noisy (dull non-union peak)
    "secondary_peak_ratio": 1.0,   # implant-loosening signature
    "band_energy_low": 0.8,
    "band_energy_mid": 0.8,
    "band_energy_high": 0.8,
}

# Blend of signal-feature similarity and comorbidity/context overlap.
FEATURE_SIM_WEIGHT = 0.7
COMORBIDITY_SIM_WEIGHT = 0.3

_EPS = 1e-9


# ── Feature helpers ──────────────────────────────────────────────────────────

def _scan_features(scan: Scan) -> Optional[dict]:
    if not scan.features_json:
        return None
    try:
        return json.loads(scan.features_json)
    except (json.JSONDecodeError, TypeError):
        return None


def _cohort_stats(scans: list[Scan]) -> dict[str, tuple[float, float]]:
    """Per-feature (mean, std) over the cohort, for z-scoring the distance."""
    cols = list(SIMILARITY_FEATURE_WEIGHTS)
    acc: dict[str, list[float]] = {c: [] for c in cols}
    for s in scans:
        feats = _scan_features(s)
        if not feats:
            continue
        for c in cols:
            v = feats.get(c)
            if v is not None:
                acc[c].append(float(v))
    stats: dict[str, tuple[float, float]] = {}
    for c, vals in acc.items():
        if len(vals) >= 2:
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
            stats[c] = (mean, math.sqrt(var) or 1.0)
        else:
            stats[c] = (0.0, 1.0)
    return stats


def _feature_distance(a: dict, b: dict, stats: dict[str, tuple[float, float]]) -> float:
    total = 0.0
    for c, w in SIMILARITY_FEATURE_WEIGHTS.items():
        va, vb = a.get(c), b.get(c)
        if va is None or vb is None:
            continue
        _, sd = stats.get(c, (0.0, 1.0))
        za, zb = float(va) / sd, float(vb) / sd
        total += w * (za - zb) ** 2
    return math.sqrt(total)


def _comorbidity_overlap(pa: Patient, pb: Patient) -> float:
    """Jaccard over the categorical risk/context set."""
    def profile(p: Patient) -> set[str]:
        s = {f"bone:{p.bone}", f"fx:{p.fracture_type}"}
        if p.smoker:
            s.add("smoker")
        if p.diabetic:
            s.add("diabetic")
        return s
    sa, sb = profile(pa), profile(pb)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Public: similar-case retrieval ───────────────────────────────────────────

def similar_scans(db: Session, scan: Scan, k: int = 5) -> list[dict]:
    """Top-K most similar prior scans from OTHER patients, preferring cases with
    a confirmed outcome. Returns display-ready dicts (no graph object)."""
    target_feats = _scan_features(scan)
    if not target_feats:
        return []
    target_patient = db.get(Patient, scan.patient_id)

    all_scans = list(db.exec(select(Scan)))
    feature_scans = [s for s in all_scans if _scan_features(s) and s.patient_id != scan.patient_id]
    stats = _cohort_stats([s for s in all_scans if _scan_features(s)])

    patients = {p.id: p for p in db.exec(select(Patient))}
    outcomes_by_scan = {o.scan_id: o for o in db.exec(select(Outcome)) if o.scan_id}

    scored: list[dict] = []
    for s in feature_scans:
        feats = _scan_features(s)
        dist = _feature_distance(target_feats, feats, stats)
        feat_sim = 1.0 / (1.0 + dist)
        other = patients.get(s.patient_id)
        comorb = _comorbidity_overlap(target_patient, other) if (target_patient and other) else 0.0
        score = FEATURE_SIM_WEIGHT * feat_sim + COMORBIDITY_SIM_WEIGHT * comorb
        outcome = outcomes_by_scan.get(s.id)
        scored.append({
            "scan_id": s.id,
            "patient_id": s.patient_id,
            "patient_code": other.patient_code if other else None,
            "patient_name": other.name if other else None,
            "week": s.week,
            "tsi_pct": s.tsi_pct,
            "predicted_label": s.predicted_label,
            "confirmed_outcome": outcome.true_label if outcome else None,
            "comorbidities": _comorbidity_list(other) if other else [],
            "distance": round(dist, 4),
            "score": round(score, 4),
            "has_outcome": outcome is not None,
        })

    # Prefer confirmed-outcome cases, then higher score.
    scored.sort(key=lambda r: (r["has_outcome"], r["score"]), reverse=True)
    return scored[:k]


def _comorbidity_list(p: Patient) -> list[str]:
    out = []
    if p.smoker:
        out.append("smoker")
    if p.diabetic:
        out.append("diabetic")
    return out


# ── Public: graph construction + patient ego-graph ───────────────────────────

def build_graph(db: Session) -> nx.MultiDiGraph:
    """Full knowledge graph over the cohort (used for the ego-graph view)."""
    g = nx.MultiDiGraph()
    patients = list(db.exec(select(Patient)))
    scans = list(db.exec(select(Scan)))
    outcomes = list(db.exec(select(Outcome)))

    for p in patients:
        g.add_node(f"patient:{p.id}", type="patient", label=p.name, code=p.patient_code,
                   status=p.status)
        g.add_node(f"bone:{p.bone}", type="bone", label=p.bone)
        g.add_edge(f"patient:{p.id}", f"bone:{p.bone}", type="of_bone")
        g.add_node(f"fx:{p.fracture_type}", type="fracture", label=p.fracture_type)
        g.add_edge(f"patient:{p.id}", f"fx:{p.fracture_type}", type="has_fracture")
        for comorb in _comorbidity_list(p):
            g.add_node(f"comorb:{comorb}", type="comorbidity", label=comorb)
            g.add_edge(f"patient:{p.id}", f"comorb:{comorb}", type="has_comorbidity")

    scans_by_patient: dict[int, list[Scan]] = {}
    for s in scans:
        scans_by_patient.setdefault(s.patient_id, []).append(s)
    for pid, plist in scans_by_patient.items():
        plist.sort(key=lambda s: (s.week, s.id or 0))
        prev = None
        for s in plist:
            g.add_node(f"scan:{s.id}", type="scan", label=f"wk {s.week:g}",
                       tsi=s.tsi_pct, traffic_light=s.traffic_light, week=s.week)
            g.add_edge(f"patient:{pid}", f"scan:{s.id}", type="has_scan")
            if prev is not None:
                g.add_edge(f"scan:{prev.id}", f"scan:{s.id}", type="progressed_to")
            prev = s

    for o in outcomes:
        g.add_node(f"outcome:{o.true_label}", type="outcome", label=o.true_label)
        if o.scan_id:
            g.add_edge(f"scan:{o.scan_id}", f"outcome:{o.true_label}", type="confirmed_outcome")
        else:
            g.add_edge(f"patient:{o.patient_id}", f"outcome:{o.true_label}", type="confirmed_outcome")
    return g


def patient_ego_graph(db: Session, patient_id: int, k_similar: int = 4) -> dict:
    """Ego-graph around one patient (self + scans + context + outcomes), plus
    similar_to edges from the patient's latest scan to the closest other-patient
    scans. Returns {nodes, edges} for visualisation."""
    g = build_graph(db)
    root = f"patient:{patient_id}"
    if root not in g:
        return {"nodes": [], "edges": []}

    # 1-2 hop neighbourhood around the patient
    keep: set[str] = {root}
    keep |= set(g.successors(root))
    for n in list(keep):
        keep |= set(g.successors(n))

    # similar_to edges from the patient's latest scan
    plist = [s for s in db.exec(select(Scan)) if s.patient_id == patient_id and s.features_json]
    plist.sort(key=lambda s: (s.week, s.id or 0))
    sim_edges: list[dict] = []
    if plist:
        latest = plist[-1]
        for sim in similar_scans(db, latest, k=k_similar):
            sid = f"scan:{sim['scan_id']}"
            pid = f"patient:{sim['patient_id']}"
            keep.add(sid)
            keep.add(pid)
            sim_edges.append({"source": f"scan:{latest.id}", "target": sid,
                              "type": "similar_to", "score": sim["score"]})

    nodes = [{"id": n, **{kk: vv for kk, vv in g.nodes[n].items()}} for n in keep if n in g]
    edges = [{"source": u, "target": v, **d}
             for u, v, d in g.edges(data=True) if u in keep and v in keep]
    edges.extend(sim_edges)
    return {"nodes": nodes, "edges": edges}
