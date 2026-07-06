"""Model-version history + continual-retrain trigger endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import ModelVersion
from app.schemas.model import (
    ModelVersionRead, ModelVersionsResponse, RetrainResponse,
)

router = APIRouter(tags=["model"])


@router.get("/api/model/versions", response_model=ModelVersionsResponse)
def model_versions(db: Session = Depends(get_session)):
    rows = list(db.exec(select(ModelVersion).order_by(ModelVersion.version)))
    active = next((r.version for r in rows if r.is_active), None)
    return ModelVersionsResponse(
        active_version=active,
        versions=[ModelVersionRead.model_validate(r) for r in rows],
    )


@router.post("/api/model/retrain", response_model=RetrainResponse, status_code=201)
def retrain(db: Session = Depends(get_session)):
    """Train a challenger on the synthetic bootstrap + all clinician-confirmed
    pairs and promote it iff it beats the champion on the frozen holdout."""
    # Imported here so a slow sklearn import doesn't affect app startup.
    from ml_retrain.retrain import retrain_challenger
    result = retrain_challenger(db)
    return RetrainResponse(
        champion_f1=result["champion_f1"],
        challenger_f1=result["challenger_f1"],
        promoted=result["promoted"],
        new_version=result["new_version"],
        clinician_pairs=result["clinician_pairs"],
        synthetic_n=result["synthetic_n"],
    )
