"""
Fairness / concentration monitor (ethics guard).

Tracks whether alert/hotspot activity concentrates over geography over time
(per-district share of flagged ATMs + Gini coefficient of concentration) so an
ops reviewer can spot over-policing patterns. Deliberately has NO demographic
dimensions — the system is anti-profiling by design (risk = transaction
behaviour + complaint linkage + transaction geography only).

Output: artifacts/fairness_report.json
Usage:  python -m backend.eval.fairness_check
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import ARTIFACT_DIR  # noqa: E402


def _gini(values: list[float]) -> float:
    x = sorted(values)
    n = len(x)
    if n == 0 or sum(x) == 0:
        return 0.0
    return float((2 * sum((i + 1) * v for i, v in enumerate(x)) / (n * sum(x))) - (n + 1) / n)


def run() -> dict:
    from backend import repositories as repo
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        alerts = repo.list_alerts(db, limit=1000)
        per_district: dict[str, int] = {}
        for a in alerts:
            per_district[a.district] = per_district.get(a.district, 0) + 1
        total = len(alerts)
        shares = sorted((v / total for v in per_district.values()), reverse=True) if total else []
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "alerts_total": total,
            "alerts_per_district": per_district,
            "top_district_share_pct": round(100 * shares[0], 1) if shares else 0.0,
            "gini_concentration": round(_gini(list(per_district.values())), 4),
            "note": (
                "Geography-only concentration monitor (no demographic dimensions — "
                "anti-profiling by design). Advisory: review if any district's share "
                "persistently dominates or Gini trends upward."
            ),
            "ethics_banner": "No automated enforcement — advisory only; audited human decision required.",
        }
    finally:
        db.close()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "fairness_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()