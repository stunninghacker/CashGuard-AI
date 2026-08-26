"""
Smoke test — guards the two defect classes from the Phase-1 fix round:

  1. Import-time errors (NameError etc.) anywhere under backend/.
  2. The drip_ingest runtime crash (models/BANKS resolution) + row insertion.
  3. metrics.json must parse and contain no NaN/Infinity tokens.

Usage:  python scripts/smoke_test.py     (prints SMOKE OK / exits non-zero)
"""
from __future__ import annotations

import importlib
import json
import random
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails: list[str] = []

# ---------------------------------------------------------------- 1. imports
import backend  # noqa: E402
import pkgutil  # noqa: E402

modules = [m.name for m in pkgutil.walk_packages(backend.__path__, prefix="backend.")]
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:  # pragma: no cover
        fails.append(f"IMPORT {name}: {exc}")
print(f"[1] imported {len(modules)} backend modules"
      + (" — FAILURES:\n  " + "\n  ".join(fails) if fails else " OK"))

# ---------------------------------------------------------------- 2. drip path
from backend.data.synthetic_data import load_calibration_config  # noqa: E402
from backend.ml.features import load_dataframes  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.database import Base  # noqa: E402

try:
    import gc
    import shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="cashguard_smoke_"))
    engine = create_engine(f"sqlite:///{tmp_dir / 'smoke.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

    from backend.data.synthetic_data import generate_all  # noqa: E402

    cfg = load_calibration_config()
    cfg["dataset"]["n_complaints"] = 100
    cfg["dataset"]["n_atms_per_city"] = 40
    cfg["dataset"]["n_withdrawals"] = 2000
    generate_all(db, cfg=cfg, seed=7)

    from backend import services  # noqa: E402

    before = len(db.query(backend.models.Complaint).all())
    inserted = services.drip_ingest(db, random.Random(0), cfg)
    after = len(db.query(backend.models.Complaint).all())
    n_wd = len(db.query(backend.models.Withdrawal).all())
    n_acct = len(db.query(backend.models.Account).all())
    if inserted <= 0:
        fails.append("drip_ingest returned non-positive")
    if after <= before:
        fails.append("drip_ingest inserted no complaint")
    if n_wd <= 0 or n_acct <= 0:
        fails.append("drip_ingest inserted no withdrawals/account rows")
    # exercising the label-only guarantee: is_fraud_withdrawal must resolve
    comp, wd, atms = load_dataframes(engine)
    if len(wd) != n_wd:
        fails.append("withdrawal count mismatch after drip")
    print(f"[2] drip_ingest -> {inserted} items, complaints {before}->{after}, "
          f"withdrawals={n_wd}, accounts={n_acct}"
          + (" — FAILURES:\n  " + "\n  ".join(fails) if fails else " OK"))
    db.close()
    engine.dispose()
    gc.collect()
    shutil.rmtree(tmp_dir, ignore_errors=True)
except Exception as exc:  # pragma: no cover
    fails.append(f"DRIP PATH: {exc}")
    print("[2] drip path raised:", exc)

# ---------------------------------------------------------------- 3. metrics.json
metrics_path = ROOT / "artifacts" / "metrics.json"
try:
    text = metrics_path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    bad = re.findall(r"\b(?:NaN|Infinity|-Infinity)\b", text)
    if bad:
        fails.append(f"metrics.json contains non-JSON tokens: {bad}")
    if not isinstance(parsed, dict):
        fails.append("metrics.json is not a JSON object")
    print(f"[3] metrics.json parses, {len(parsed)} keys, NaN/Infinity tokens: {bad or 'none'}"
          + (" — FAILURES:\n  " + "\n  ".join(fails) if fails else " OK"))
except Exception as exc:  # pragma: no cover
    fails.append(f"METRICS JSON: {exc}")
    print("[3] metrics.json unreadable:", exc)

if fails:
    print("\nSMOKE FAIL")
    sys.exit(1)
print("\nSMOKE OK")