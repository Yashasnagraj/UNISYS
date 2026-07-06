"""
Generate an HONEST fallback replay fixture from the realistic capture-batch
model (press-to-press jitter + bad-contact misses). Used ONLY when a live
device capture is unavailable on stage — real captured sweeps from
`tools/capture_batch.py` always take precedence and should overwrite this file.

Usage (from backend/):
    python -m tools.make_fallback_fixture --name demo_tibia --f-peak 235 --sweeps 40
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.services.sim_source import make_capture_batch  # noqa: E402

FIXTURES_DIR = os.path.join(_BACKEND_ROOT, "fixtures")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate an honest synthetic fallback fixture.")
    ap.add_argument("--name", default="demo_tibia")
    ap.add_argument("--f-peak", type=float, default=235.0)
    ap.add_argument("--sweeps", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    data = make_capture_batch(f_peak=args.f_peak, n_sweeps=args.sweeps, seed=args.seed)
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    path = os.path.join(FIXTURES_DIR, f"{args.name}.json")
    payload = {
        "fs": float(data["fs"]),
        "sweeps": [[float(x) for x in s] for s in data["sweeps"]],
        "meta": {
            "name": args.name,
            "synthetic": True,   # HONESTY: this is a fallback, not real hardware
            "note": "synthetic fallback (press-to-press jitter model); overwrite with real captures",
            "f_peak_target": args.f_peak,
            "n_sweeps": args.sweeps,
        },
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    print(f"wrote {args.sweeps} synthetic sweeps -> {path}  (synthetic=True)")


if __name__ == "__main__":
    main()
