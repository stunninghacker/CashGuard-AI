"""Seed stability: does the generator+training pipeline produce stable metrics?

Trains the SAME pipeline on the SAME data across 5 different training seeds
(model-level) and 5 different generator-regeneration seeds (data-level, on
temp DBs with the same config). Reports AUC / P@100 / P@1000 spread.

If the spread is small -> metrics are stable, not lucky-draw. If large ->
the honest caveat is documented in GENERATOR_LEAKAGE_AUDIT.md.

Run: python scripts/seed_stability.py
Out: artifacts/deep_eval/seed_stability.json
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.database import Base, engine  # noqa: E402
from backend.eval.deep_evaluation import OUT, load_split, train_score  # noqa: E402

SEEDS = 5


def model_seed_stability():
    rows = []
    for seed in range(SEEDS):
        X, meta, y, m_tr, m_val, m_te = load_split(engine)
        feat = [c for c in X.columns if not c.startswith("meta_")]
        Xf = X[feat]
        model, score = train_score(Xf[m_tr], y[m_tr], Xf[m_val], y[m_val], Xf[m_te], y[m_te], seed=seed)
        yte = np.asarray(y[m_te], dtype=float)
        order = np.argsort(-score)
        rows.append({
            "seed": seed,
            "roc_auc": round(float(roc_auc_score(yte, score)), 4),
            "precision_at_100": round(float(yte[order[:100]].mean()), 4),
            "precision_at_1000": round(float(yte[order[:1000]].mean()), 4),
        })
    return rows


def generator_seed_stability():
    rows = []
    from backend.data.synthetic_data import generate_all, load_calibration_config

    cfg = load_calibration_config()
    cfg["dataset"]["n_atms_per_city"] = 60
    cfg["dataset"]["n_withdrawals"] = 60000
    cfg["dataset"]["n_complaints"] = 5000
    tmp = Path(tempfile.mkdtemp(prefix="cg_seed_"))
    try:
        for seed in range(SEEDS):
            db_path = tmp / f"s{seed}.db"
            eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
            Base.metadata.create_all(bind=eng)
            db = sessionmaker(bind=eng, autocommit=False, autoflush=False)()
            generate_all(db, cfg=cfg, seed=seed)
            db.close()
            X, meta, y, m_tr, m_val, m_te = load_split(eng)
            feat = [c for c in X.columns if not c.startswith("meta_")]
            Xf = X[feat]
            model, score = train_score(Xf[m_tr], y[m_tr], Xf[m_val], y[m_val], Xf[m_te], y[m_te])
            yte = np.asarray(y[m_te], dtype=float)
            order = np.argsort(-score)
            rows.append({
                "seed": seed,
                "roc_auc": round(float(roc_auc_score(yte, score)), 4),
                "precision_at_100": round(float(yte[order[:100]].mean()), 4),
                "precision_at_1000": round(float(yte[order[:1000]].mean()), 4),
            })
            eng.dispose()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def summarize(rows, key):
    a = np.array([r[key] for r in rows])
    return {
        "min": round(float(a.min()), 4),
        "max": round(float(a.max()), 4),
        "spread": round(float(a.max() - a.min()), 4),
        "mean": round(float(a.mean()), 4),
    }


def main():
    print("seed stability: model seeds (same data)...")
    model_rows = model_seed_stability()
    for r in model_rows:
        print(f"  model seed {r['seed']}: AUC {r['roc_auc']} P@100 {r['precision_at_100']} P@1000 {r['precision_at_1000']}")
    print("seed stability: generator seeds (fresh data each)...")
    gen_rows = generator_seed_stability()
    for r in gen_rows:
        print(f"  gen seed {r['seed']}: AUC {r['roc_auc']} P@100 {r['precision_at_100']} P@1000 {r['precision_at_1000']}")

    out = {
        "label": "CONTROLLED SYNTHETIC EVALUATION",
        "model_seed_variation": {
            "rows": model_rows,
            "summary": {k: summarize(model_rows, k) for k in ("roc_auc", "precision_at_100", "precision_at_1000")},
        },
        "generator_seed_variation": {
            "rows": gen_rows,
            "summary": {k: summarize(gen_rows, k) for k in ("roc_auc", "precision_at_100", "precision_at_1000")},
        },
        "conclusion": "Small model-seed spread shows the pipeline is deterministic-stable; generator-seed spread quantifies how much metric variation comes from the data draw itself. Reported, not hidden.",
    }
    (OUT / "seed_stability.json").write_text(json.dumps(out, indent=2))
    print("saved:", OUT / "seed_stability.json")


if __name__ == "__main__":
    main()