"""Schemas for the model-version / continual-retrain endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.schemas.patient import CamelModel


class ModelVersionRead(CamelModel):
    id: int
    version: int
    synthetic_n: int
    clinician_pairs: int
    macro_f1_holdout: float
    champion_f1: Optional[float] = None
    promoted: bool
    is_active: bool
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class ModelVersionsResponse(CamelModel):
    active_version: Optional[int] = None
    versions: list[ModelVersionRead]


class RetrainResponse(CamelModel):
    champion_f1: float
    challenger_f1: float
    promoted: bool
    new_version: int
    clinician_pairs: int
    synthetic_n: int
