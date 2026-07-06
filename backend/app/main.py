"""ResoScan FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import init_db
from app.engine_bridge import engine_health
from app.routers import graph, model, patients, scans


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # seed demo patients + backfill device-domain feature scans (both idempotent)
    from app.db.seed import backfill_demo_features, seed_demo_patients
    seeded = seed_demo_patients()
    backfilled = backfill_demo_features()
    app.state.seeded = seeded
    app.state.backfilled = backfilled
    # NB: the single-scan champion (v1) is established lazily on the first
    # /api/model/retrain call — see ml_retrain.retrain.retrain_challenger — so the
    # committed model.pkl is only swapped at that explicit moment, not on boot.
    yield


app = FastAPI(title="ResoScan API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(scans.router)
app.include_router(graph.router)
app.include_router(model.router)


@app.get("/api/health")
def health():
    eng = engine_health()
    return {
        "status": "ok" if eng.get("engine_ok") else "degraded",
        "device_port": settings.device_port,
        **eng,
    }
