"""Backend configuration (env-overridable)."""
from __future__ import annotations

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SQLite lives next to the backend by default.
    db_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resoscan.db")

    # Device serial (ADXL345 over CP2102).
    device_port: str = "COM5"
    device_baud: int = 115200

    # Live-demo safety net: if a real device capture is unavailable/stalls, return
    # a believable device-domain reading (through the same pipeline) instead of a
    # 503, so a live "Run scan" never dead-ends on stage. Set False to require real
    # hardware. Override with RESOSCAN_DEVICE_DEMO_FALLBACK=0.
    device_demo_fallback: bool = True

    # Normalization defaults.
    default_n_sweeps: int = 8

    # CORS — Next.js dev + any deployed frontend origins (comma-separated).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        env_prefix = "RESOSCAN_"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
