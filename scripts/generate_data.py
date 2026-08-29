"""
Generate the full synthetic dataset (calibrated, source-tagged).

Usage:
    python scripts/generate_data.py
    python scripts/generate_data.py --complaints 12000 --withdrawals 200000 --months 6

Before generating, prints the CALIBRATION SUMMARY — every parameter and its
source_status (verified_pattern | assumption_general_literature).

Output: SQLite DB at data/cashguard.db + CSVs in data/ (for inspection).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import DATA_DIR, SEED  # noqa: E402
from backend.data.synthetic_data import (  # noqa: E402
    generate_all,
    load_calibration_config,
    print_calibration_summary,
)
from backend.database import SessionLocal, init_db  # noqa: E402


def export_csvs() -> None:
    """Snapshot the DB tables to CSV for judges / notebooks."""
    import pandas as pd

    from backend.database import engine

    for table in ("complaints", "atms", "withdrawals", "accounts", "transfers", "vault", "alerts", "audit_log", "recovery_recommendations", "reports", "inbox"):
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", engine)
            df.to_csv(DATA_DIR / f"{table}.csv", index=False)
            print(f"  exported data/{table}.csv ({len(df):,} rows)")
        except Exception as exc:
            print(f"  skipped {table}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic NCRP/ATM data (calibrated)")
    parser.add_argument("--complaints", type=int, default=None)
    parser.add_argument("--atms-per-city", type=int, default=None)
    parser.add_argument("--withdrawals", type=int, default=None)
    parser.add_argument("--fraud-share", type=float, default=None)
    parser.add_argument("--months", type=int, default=None)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--no-csv", action="store_true", help="skip CSV export")
    args = parser.parse_args()

    cfg = load_calibration_config()
    if args.complaints:
        cfg["dataset"]["n_complaints"] = args.complaints
    if args.atms_per_city:
        cfg["dataset"]["n_atms_per_city"] = args.atms_per_city
    if args.withdrawals:
        cfg["dataset"]["n_withdrawals"] = args.withdrawals
    if args.fraud_share is not None:
        cfg["dataset"]["fraud_share"] = args.fraud_share
    if args.months:
        cfg["dataset"]["months"] = args.months

    print_calibration_summary(cfg)  # honesty requirement: visible source tagging

    DATA_DIR.mkdir(exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        # Wipe existing synthetic rows so regeneration is idempotent.
        from backend import models  # noqa: E402

        for table in (
            models.RecoveryRecommendation, models.Report, models.InboxMessage,
            models.AuditRecord, models.Alert, models.Withdrawal, models.Transfer,
            models.Account, models.Complaint, models.ATM, models.VaultEntry, models.User,
        ):
            db.query(table).delete()
        db.commit()
        print("Cleared existing synthetic rows.")

        # re-seed the four demo users (auth/RBAC) — also done on app startup
        from backend.repositories import seed_demo_users  # noqa: E402

        seed_demo_users(db)

        summary = generate_all(db, cfg=cfg, seed=args.seed)
        print("Synthetic data generated:")
        for k, v in summary.items():
            print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
        if not args.no_csv:
            export_csvs()
    finally:
        db.close()


if __name__ == "__main__":
    main()