"""SQLite engine + session dependency."""
from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False so FastAPI's threadpool can share the connection.
engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


def _migrate() -> None:
    """Add columns introduced after initial schema (SQLite ALTER TABLE)."""
    new_columns = [
        "ALTER TABLE scans ADD COLUMN stages_json TEXT",
        "ALTER TABLE scans ADD COLUMN norm_psd_json TEXT",
    ]
    with engine.connect() as conn:
        for sql in new_columns:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists


def init_db() -> None:
    # Import models so SQLModel.metadata is populated before create_all.
    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate()


def get_session():
    with Session(engine) as session:
        yield session
