"""
Train the ML model on the synthetic dataset.

Usage:
    python scripts/train_model.py
    python scripts/train_model.py --days-back 90   (faster retrains)

Output: artifacts/model.joblib + artifacts/metrics.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import METRICS_PATH  # noqa: E402
from backend.database import engine  # noqa: E402
from backend.ml.train import train  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the hotspot classifier")
    parser.add_argument("--days-back", type=int, default=None, help="restrict training to last N days")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    metrics = train(engine, days_back=args.days_back, seed=args.seed)
    print(json.dumps(metrics, indent=2))
    print(f"Model saved to {METRICS_PATH.parent / 'model.joblib'}")


if __name__ == "__main__":
    main()