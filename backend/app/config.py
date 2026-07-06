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

    # Capture transport: 'serial' (USB), 'wifi' (HTTP to device_host), or 'auto'
    # (Wi-Fi if device_host is set/reachable, else serial). Wi-Fi also sidesteps
    # the COM-port locking (only one app can hold a serial port).
    device_transport: str = "serial"
    device_host: str = ""          # ESP32 IP/host for Wi-Fi pull, e.g. "192.168.1.50"

    # Read real captures from the Wi-Fi CSV written by tools/capture.py (columns:
    # N,Z — sample index, raw Z counts, at the firmware ODR). When set, a device
    # scan reads the newest sweep from this file. TAKES PRIORITY over device_log_path.
    device_csv_path: str = ""      # e.g. "D:/UNISYS_2026/resoscan_data.csv"
    device_csv_fs_hz: float = 3200.0   # firmware ODR (sample N is at N/fs seconds)

    # Read real captures from a terminal LOG file (PuTTY "All session output").
    # When set, a device scan reads the newest complete block from this file —
    # PuTTY keeps the serial link, we consume its log (no COM-port fight).
    device_log_path: str = ""      # e.g. "C:/Users/yashr/Downloads/reso_live.log"

    # Live-demo safety net: if a real device capture is unavailable/stalls, return
    # a believable device-domain reading (through the same pipeline) instead of a
    # 503, so a live "Run scan" never dead-ends on stage. Set False to require real
    # hardware. Override with RESOSCAN_DEVICE_DEMO_FALLBACK=0.
    device_demo_fallback: bool = True

    # When the demo fallback is active, prefer replaying this batch fixture
    # (real captured sweeps → a genuine repeatability collapse) over a single
    # clean synthetic sweep. Falls back to the synthetic device sim if the
    # fixture is missing. Set empty to force the old single-sweep sim.
    device_demo_fixture: str = "demo_tibia"

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
