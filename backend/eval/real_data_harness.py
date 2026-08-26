"""
Real-data validation harness (Phase 2 — grounding).

Purpose: a concrete, runnable path to answer "your model only learns your
generator." This harness ingests REAL/PUBLIC aggregate complaint counts from
data/real/ and checks whether the framework's predicted hotspot density
correlates with real complaint density.

Schema (data/real/*.csv — one file is enough):
    district, date, complaint_count
  district: any string. If it matches a FICTIONAL district name used by the
            framework (Northsagar, Metro-West, Greenfield, District-3,
            Eastvale), the harness computes a Spearman correlation between the
            predicted hotspot density per district and the real complaint
            counts. Real NCRP/I4C/RBI aggregate exports can be dropped in
            without code changes.

If data/real/ is empty (or contains no matching districts) the harness writes
    {"status": "PENDING_REAL_DATA", "harness": "ready", ...}
and NEVER invents numbers.

Usage: python -m backend.eval.real_data_harness
Output: artifacts/real_validation.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import ARTIFACT_DIR, DATA_DIR  # noqa: E402


def _hotspot_density_by_district(db) -> dict[str, float]:
    """Predicted hotspot density per district (share of ATMs above 0.7)."""
    from backend import repositories as repo
    from backend.services import get_risk_scores, resolve_as_of

    ref = resolve_as_of(db)
    scores = get_risk_scores(db, as_of=ref)
    per: dict[str, list[float]] = {}
    for s in scores:
        per.setdefault(s["district"], []).append(s["risk_score"])
    return {d: sum(1 for x in v if x >= 0.7) / len(v) for d, v in per.items()}


def run() -> dict:
    real_dir = DATA_DIR / "real"
    csvs = sorted(real_dir.glob("*.csv")) if real_dir.exists() else []
    result: dict = {
        "generated_at": datetime.utcnow().isoformat(),
        "harness": "ready",
        "real_files_found": [p.name for p in csvs],
    }
    if not csvs:
        result["status"] = "PENDING_REAL_DATA"
        result["note"] = "data/real/ is empty — drop a CSV (district, date, complaint_count) to validate."
        result["spearman_rho"] = None
        result["n_real_rows"] = 0
        _write(result)
        return result

    frames = [pd.read_csv(p) for p in csvs]
    real = pd.concat(frames, ignore_index=True)
    required = {"district", "date", "complaint_count"}
    if not required.issubset(real.columns):
        result["status"] = "PENDING_REAL_DATA"
        result["note"] = f"CSV schema mismatch — need columns {sorted(required)}, got {list(real.columns)}."
        result["spearman_rho"] = None
        result["n_real_rows"] = int(len(real))
        _write(result)
        return result

    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        density = _hotspot_density_by_district(db)
    finally:
        db.close()

    real_by_district = real.groupby("district")["complaint_count"].sum()
    common = sorted(set(density) & set(real_by_district.index))
    if len(common) < 3:
        result["status"] = "PENDING_REAL_DATA"
        result["note"] = f"No matching districts: framework={sorted(density)}, real={sorted(real_by_district.index)}."
        result["spearman_rho"] = None
        result["n_real_rows"] = int(len(real))
        _write(result)
        return result

    from scipy.stats import spearmanr  # may not exist; fallback below

    try:
        rho = spearmanr([density[d] for d in common], [int(real_by_district[d]) for d in common]).statistic
    except Exception:  # scipy missing
        import numpy as np

        x = np.array([density[d] for d in common])
        y = np.array([int(real_by_district[d]) for d in common])
        rho = float(np.corrcoef(np.argsort(x), np.argsort(y))[0, 1])

    result["status"] = "VALIDATED"
    result["spearman_rho"] = round(float(rho), 4)
    result["n_matched_districts"] = len(common)
    result["matched_districts"] = common
    result["note"] = "Predicted hotspot density vs real complaint density (Spearman rho)."
    _write(result)
    return result


def _write(result: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "real_validation.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run()