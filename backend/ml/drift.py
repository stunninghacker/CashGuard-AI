"""
Live feature-drift monitor (Issue 11).

Monitors Population Stability Index (PSI) of the model's input feature
distributions between the *reference* distribution captured at training time
and the *current* streaming window. A feature whose PSI exceeds a threshold is
a candidate for model drift — the model may be scoring on data unlike what it
saw during training, so its calibration/ranking can be trusted less.

Honest scope:
- PSI is computed on the SAME feature pipeline the model actually uses
  (`build_features`), so there is no train/serve skew in the monitoring signal.
- We compare a **reference snapshot** (taken at training `as_of`) against a
  **current window**. Until a reference snapshot exists, the monitor reports
  `PENDING_REFERENCE` — it does NOT fabricate a baseline.
- A high PSI triggers an alert + a *retrain request marker* (ops decide to act,
  training is not auto-run blind on a tiny window). This matches the repo's
  "never auto-retrains on tiny data" discipline.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from ..config import ARTIFACT_DIR, MODEL_PATH
from ..database import engine, SessionLocal
from . import inference
from .features import build_features

DRIFT_FEATURES = [
    # complaint surge signals
    "n_complaints_city_24h", "n_complaints_city_7d",
    "n_complaints_district_24h", "t_phishing_7d",
    # ATM withdrawal behaviour
    "withdrawals_1h", "withdrawals_6h", "withdrawals_24h",
    "amount_sum_24h", "distinct_accounts_24h", "linked_proportion_24h",
    # behavioural signature
    "transaction_frequency_24h", "counterparty_count_24h", "fund_velocity_24h",
    "hawkes_intensity_24h",
    # geospatial
    "dist_to_complaint_centroid_km", "dist_to_city_center_km",
    # Issue-1 features
    "complaint_decay_5km", "complaint_surge_velocity", "mule_reuse_count_7d",
    "pin_corridor_dist_km", "bank_fraud_rate_hist", "night_ratio_24h",
    "amount_mean_7d", "amount_max_7d",
]

PSI_ALERT_THRESHOLD = 0.20   # retrain / HOLD-aggressive-confidence trigger (spec)
PSI_WARN_THRESHOLD = 0.10    # yellow band: surface reduced confidence, no retrain
BINS = 10
CACHE_TTL_SECONDS = 600
DRIFT_DIR = ARTIFACT_DIR / "drift"


def _psi(actual_pct: np.ndarray, expected_pct: np.ndarray) -> float:
    """Population Stability Index between two decile-share vectors."""
    eps = 1e-6
    actual_pct = np.clip(np.asarray(actual_pct, dtype=float), eps, None)
    expected_pct = np.clip(np.asarray(expected_pct, dtype=float), eps, None)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def _feature_matrix(as_of: datetime):
    """Rebuild the model's feature matrix for a given forecast day."""
    pipe = inference.load_pipeline()
    feature_day = as_of.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    X, meta = build_features(
        engine,
        [feature_day],
        hawkes_params=pipe.get("hawkes_params"),
        fraud_latency_by_type=pipe.get("fraud_latency_by_type") or {},
        bank_fraud_rate=pipe.get("bank_fraud_rate") or {},
    )
    return X, meta


def _decile_profiles(X, features):
    """Return {feature: {'edges': [...], 'expected_pct': [...]}} reference bins."""
    profiles = {}
    for f in features:
        if f not in X.columns:
            continue
        col = X[f].astype(float).fillna(0.0).to_numpy()
        q = np.quantile(col, np.linspace(0, 100, BINS + 1) / 100)
        # dedupe bin edges so np.digitize/quantile are well-defined for 0-inflated cols
        q = np.unique(q)
        hist, _ = np.histogram(col, bins=q if len(q) > 1 else np.array([float(col.min())-1, float(col.max())+1]))
        counts = hist / max(hist.sum(), 1)
        profiles[f] = {"edges": q.tolist(), "expected_pct": counts.tolist()}
    return profiles


def _psi_vs_reference(X, profiles):
    """Per-feature PSI of the current matrix vs the reference profiles."""
    result = {}
    for f, prof in profiles.items():
        if f not in X.columns:
            continue
        col = X[f].astype(float).fillna(0.0).to_numpy()
        edges = np.asarray(prof["edges"])
        if len(edges) > 1:
            actual, _ = np.histogram(col, bins=edges)
        else:
            actual = np.zeros(len(prof["expected_pct"]))
            actual[0] = len(col)
        actual_pct = actual / max(actual.sum(), 1)
        expected_pct = np.asarray(prof["expected_pct"])
        if len(expected_pct) != len(actual_pct):
            # zero-inflated column collapse — pad expected to match actual bins
            expected_pct = np.resize(expected_pct, len(actual_pct))
            expected_pct = expected_pct / max(expected_pct.sum(), 1)
        result[f] = round(_psi(actual_pct, expected_pct), 4)
    return result


def reference_exists() -> bool:
    return (DRIFT_DIR / "reference.json").exists()


def capture_reference(as_of: datetime | None = None) -> dict:
    """Persist the reference feature-distribution snapshot (training window)."""
    DRIFT_DIR.mkdir(parents=True, exist_ok=True)
    as_of = as_of or (datetime.now() - timedelta(days=1))
    X, _ = _feature_matrix(as_of)
    profiles = _decile_profiles(X, DRIFT_FEATURES)
    payload = {
        "captured_at": datetime.utcnow().isoformat(),
        "as_of": as_of.isoformat(),
        "n_atms": int(len(X)),
        "features": profiles,
    }
    (DRIFT_DIR / "reference.json").write_text(json.dumps(payload, indent=2))
    return payload


class DriftMonitor:
    """Compute + persist drift status and surface alerts / retrain requests."""

    def __init__(self, threshold: float = PSI_ALERT_THRESHOLD):
        self.threshold = threshold
        self._cache: dict = {"key": None, "payload": None, "ts": 0.0}

    def status(self, db, as_of: datetime | None = None, refresh: bool = False) -> dict:
        from time import time

        if not reference_exists():
            return {
                "status": "PENDING_REFERENCE",
                "note": "No reference distribution captured yet. Run capture_reference() "
                        "at training time first.",
                "threshold": self.threshold,
                "features": {}, "summary": None,
            }
        ref = json.loads((DRIFT_DIR / "reference.json").read_text())
        cache_key = str(as_of)
        if (not refresh and self._cache["key"] == cache_key
                and time() - self._cache["ts"] < CACHE_TTL_SECONDS):
            return self._cache["payload"]

        as_of = as_of or (datetime.now() - timedelta(hours=1))
        X, _ = _feature_matrix(as_of)
        psi = _psi_vs_reference(X, ref["features"])
        flagged = {f: v for f, v in psi.items() if v > self.threshold}
        warned = {f: v for f, v in psi.items() if self.threshold >= v > PSI_WARN_THRESHOLD}
        state = "red" if flagged else ("yellow" if warned else "green")
        report = {
            "status": state,
            "threshold": self.threshold,
            "warn_threshold": PSI_WARN_THRESHOLD,
            "as_of": as_of.isoformat(),
            "n_features": len(psi),
            "n_flagged": len(flagged),
            "flagged": flagged,
            "warned": warned,
            "max_psi": round(max(psi.values()), 4) if psi else 0.0,
            "summary": {
                "verdict": {
                    "red": "Retrain recommended — feature drift > {:.0%}.".format(self.threshold),
                    "yellow": "Moderate drift — reduced confidence, monitor closely.",
                    "green": "No material feature drift.",
                }[state],
                "retrain_triggered": len(flagged) > 0,
            },
        }
        self._cache = {"key": cache_key, "payload": report, "ts": time()}
        self._append_history(report)
        return report

    def check_and_alert(self, db, actor: str = "drift-monitor") -> dict:
        """Run status and, on red (retrain) or yellow, emit ledger + WS + inbox alerts."""
        report = self.status(db, refresh=True)
        if report["status"] in ("red", "yellow"):
            self._alert(db, actor, report)
        return report

    def _alert(self, db, actor: str, report: dict) -> None:
        from .. import repositories as repo
        from ..realtime import enqueue_broadcast

        repo.append_ledger(
            db, actor=actor,
            event_type="model_drift_" + report["status"],
            entity_id=f"drift-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            payload={"status": report["status"], "n_flagged": report["n_flagged"],
                     "flagged": report["flagged"]},
        )
        enqueue_broadcast("drift", {"status": report["status"],
                                    "n_flagged": report["n_flagged"],
                                    "max_psi": report["max_psi"],
                                    "flagged": report["flagged"]})
        repo.store_inbox_message(db, channel="email", payload={
            "subject": f"CashGuard model {report['status'].upper()} — feature drift alert",
            "body": report["summary"]["verdict"],
        })
        # retrain request marker (ops-gated; no blind auto-retrain on tiny window)
        DRIFT_DIR.mkdir(parents=True, exist_ok=True)
        (DRIFT_DIR / "retrain_request.json").write_text(json.dumps({
            "requested_at": datetime.utcnow().isoformat(),
            "reason": report["summary"]["verdict"],
            "flagged_features": report["flagged"],
            "auto_retrain": False,  # ops must approve; guardrail against tiny-data retrain
        }, indent=2))
        db.commit()

    def _append_history(self, report: dict) -> None:
        DRIFT_DIR.mkdir(parents=True, exist_ok=True)
        history_path = DRIFT_DIR / "history.json"
        try:
            history = json.loads(history_path.read_text() or "[]")
        except Exception:
            history = []
        history.append({
            "ts": datetime.utcnow().isoformat(),
            "status": report["status"],
            "as_of": report.get("as_of"),
            "n_flagged": report["n_flagged"],
            "max_psi": report["max_psi"],
            "flagged": report["flagged"],
        })
        history = history[-200:]
        history_path.write_text(json.dumps(history, indent=2))
