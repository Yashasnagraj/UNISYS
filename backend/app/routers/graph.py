"""Knowledge-graph and causal-explanation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.database import get_session
from app.db.models import Patient, Scan
from app.schemas.graph import (
    CausalExplanation, CausalFactor, EgoGraph, SimilarCase, SimilarCasesResponse,
)
from app.services import causal, knowledge_graph

router = APIRouter(tags=["graph"])


@router.get("/api/graph/patient/{patient_id}", response_model=EgoGraph)
def patient_graph(patient_id: int, db: Session = Depends(get_session)):
    if not db.get(Patient, patient_id):
        raise HTTPException(404, f"patient {patient_id} not found")
    ego = knowledge_graph.patient_ego_graph(db, patient_id)
    return EgoGraph(patient_id=patient_id, nodes=ego["nodes"], edges=ego["edges"])


@router.get("/api/scans/{scan_id}/similar", response_model=SimilarCasesResponse)
def scan_similar(scan_id: int, k: int = 5, db: Session = Depends(get_session)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(404, f"scan {scan_id} not found")
    cases = knowledge_graph.similar_scans(db, scan, k=k)
    return SimilarCasesResponse(
        scan_id=scan_id, cases=[SimilarCase(**c) for c in cases],
    )


@router.get("/api/scans/{scan_id}/causal", response_model=CausalExplanation)
def scan_causal(scan_id: int, db: Session = Depends(get_session)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(404, f"scan {scan_id} not found")
    patient = db.get(Patient, scan.patient_id)
    if not patient:
        raise HTTPException(404, f"patient {scan.patient_id} not found")
    n_similar = len(knowledge_graph.similar_scans(db, scan, k=5))
    exp = causal.explain_verdict(patient, scan, n_similar=n_similar)
    return CausalExplanation(
        scan_id=scan_id,
        verdict=exp["verdict"],
        n_similar=exp["n_similar"],
        active_factors=[CausalFactor(**f) for f in exp["active_factors"]],
        narrative=exp["narrative"],
    )
