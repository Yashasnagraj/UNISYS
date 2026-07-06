"""
Shared pytest fixtures.

Points the app at an isolated temp SQLite DB (set BEFORE any app import so the
engine binds to it), and provides a `db` fixture that gives each test a freshly
created schema. Fast, deterministic, no network.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TMP = tempfile.mkdtemp(prefix="reso_pytest_")
os.environ["RESOSCAN_DB_PATH"] = os.path.join(_TMP, "test.db")

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.db.database import engine, init_db  # noqa: E402


@pytest.fixture()
def db():
    """Fresh schema per test."""
    init_db()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
