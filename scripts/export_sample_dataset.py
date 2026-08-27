"""Export a small sample dataset package for the SIH submission placeholder.

Writes data/sample_dataset/ with head samples of the synthetic data:
complaints, withdrawals, atms, accounts (+ a README). Synthetic only.
Run: python scripts/export_sample_dataset.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal  # noqa: E402
from backend import models  # noqa: E402

OUT = ROOT / "data" / "sample_dataset"
OUT.mkdir(parents=True, exist_ok=True)

db = SessionLocal()
try:
    comps = db.query(models.Complaint).order_by(models.Complaint.filing_timestamp.desc()).limit(2000).all()
    wds = db.query(models.Withdrawal).order_by(models.Withdrawal.timestamp.desc()).limit(5000).all()
    atms = db.query(models.ATM).all()
    accs = db.query(models.Account).order_by(models.Account.first_seen.desc()).limit(1000).all()
finally:
    db.close()

def write_csv(name, rows, cols):
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([getattr(r, c) for c in cols])

write_csv("complaints.csv", comps,
          ["complaint_id", "filing_timestamp", "complaint_type", "victim_city",
           "victim_district", "victim_state", "victim_pin", "amount_lost",
           "linked_account_token", "status"])
write_csv("withdrawals.csv", wds,
          ["transaction_id", "timestamp", "atm_id", "account_token", "amount",
           "channel", "is_fraud_withdrawal"])
write_csv("atms.csv", atms,
          ["atm_id", "bank_name", "branch_name", "city", "district", "state",
           "pin", "police_station_area", "latitude", "longitude"])
write_csv("accounts.csv", accs,
          ["account_token", "home_bank", "first_seen", "is_mule",
           "txn_frequency_7d", "counterparty_count_7d"])

readme = """# SAMPLE DATASET (placeholder)

SYNTHETIC sample of the CashGuard-AI dataset — NOT real NCRP/bank data.
Exported by `python scripts/export_sample_dataset.py` for the SIH submission
dataset field. Columns match the production data contract
(REAL_DATA_READINESS.md). PII is already tokenized (`acct_…`/`tel_…`).
"""
(OUT / "README.txt").write_text(readme, encoding="utf-8")
print(f"sample dataset written to {OUT}: "
      f"{len(comps)} complaints, {len(wds)} withdrawals, {len(atms)} atms, {len(accs)} accounts")