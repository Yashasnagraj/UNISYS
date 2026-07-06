"""Response/request schemas for the knowledge-graph, causal, and HITL endpoints."""
from __future__ import annotations

from typing import Any, Optional

from app.schemas.patient import CamelModel


# ── GET /scans/{id}/similar ──────────────────────────────────────────────────

class SimilarCase(CamelModel):
    scan_id: int
    patient_id: int
    patient_code: Optional[str] = None
    patient_name: Optional[str] = None
    week: float
    tsi_pct: Optional[float] = None
    predicted_label: Optional[str] = None
    confirmed_outcome: Optional[str] = None
    comorbidities: list[str] = []
    distance: float
    score: float
    has_outcome: bool


class SimilarCasesResponse(CamelModel):
    scan_id: int
    cases: list[SimilarCase]


# ── GET /scans/{id}/causal ───────────────────────────────────────────────────

class CausalFactor(CamelModel):
    factor: str
    value: str
    sign: int
    weight: float
    citation: str


class CausalExplanation(CamelModel):
    scan_id: int
    verdict: str
    n_similar: int
    active_factors: list[CausalFactor]
    narrative: str


# ── GET /graph/patient/{id} ──────────────────────────────────────────────────

class EgoGraph(CamelModel):
    patient_id: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


# ── POST /scans/{id}/confirm ─────────────────────────────────────────────────

class ConfirmRequest(CamelModel):
    agree: bool = True
    override_label: Optional[str] = None   # one of LABEL_NAMES when disagreeing
    clinician: Optional[str] = None
    notes: Optional[str] = None


class ConfirmResponse(CamelModel):
    scan_id: int
    feedback_id: int
    agree: bool
    override_label: Optional[str] = None


# ── POST /scans/{id}/outcome ─────────────────────────────────────────────────

class OutcomeRequest(CamelModel):
    true_label: str                        # one of LABEL_NAMES
    weeks_to_walk: Optional[float] = None
    rust_16w: Optional[int] = None


class OutcomeResponse(CamelModel):
    outcome_id: int
    patient_id: int
    scan_id: Optional[int] = None
    true_label: str
