# validate_kaggle_vs_synthetic.py
"""Validate synthetic complaint generator against a public Kaggle cyber‑crime dataset.
The Kaggle dataset is expected to be extracted under `data/real/kaggle_cybercrime/`.
We compare the category distribution of the synthetic `data/complaints.csv`
with the real Kaggle distribution and ensure the absolute difference for every
category is ≤ 8 %.
"""

import json
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
KAGGLE_DIR = ROOT / "data" / "real" / "kaggle_cybercrime"
REAL_CSV = KAGGLE_DIR / "cybercrime_india.csv"  # assumed name
SYNTHETIC_CSV = ROOT / "data" / "complaints.csv"
THRESHOLD = 8.0  # percent

def load_real_distribution():
    if not REAL_CSV.exists():
        sys.stderr.write(f"[ERROR] Kaggle CSV not found at {REAL_CSV}. Run fetch_kaggle_cybercrime.py first.\n")
        sys.exit(1)
    df = pd.read_csv(REAL_CSV)
    if "category" not in df.columns:
        # try alternative column names
        possible = [c for c in df.columns if "type" in c.lower() or "category" in c.lower()]
        if not possible:
            sys.stderr.write("[ERROR] Cannot locate 'category' column in Kaggle data.\n")
            sys.exit(1)
        df = df.rename(columns={possible[0]: "category"})
    total = len(df)
    pct = df["category"].value_counts(normalize=True) * 100
    return pct.to_dict()

def load_synthetic_distribution():
    if not SYNTHETIC_CSV.exists():
        sys.stderr.write(f"[ERROR] Synthetic complaints file not found at {SYNTHETIC_CSV}.\n")
        sys.exit(1)
    df = pd.read_csv(SYNTHETIC_CSV)
    col = "complaint_type" if "complaint_type" in df.columns else (
        "category" if "category" in df.columns else None
    )
    if col is None:
        sys.stderr.write("[ERROR] Synthetic CSV missing 'complaint_type' column.\n")
        sys.exit(1)
    pct = df[col].value_counts(normalize=True) * 100
    return pct.to_dict()

def main():
    real = load_real_distribution()
    synth = load_synthetic_distribution()
    all_cats = set(real) | set(synth)
    passed = True
    print("\n| Category | Synthetic % | Real % | Diff % | Status |")
    print("|---|---|---|---|---|")
    for cat in sorted(all_cats):
        sp = synth.get(cat, 0.0)
        rp = real.get(cat, 0.0)
        diff = abs(sp - rp)
        status = "OK" if diff <= THRESHOLD else "FAIL"
        if status == "FAIL":
            passed = False
        print(f"| {cat} | {sp:6.2f} | {rp:6.2f} | {diff:6.2f} | {status} |")
    print("\nValidation", "PASSED" if passed else "FAILED")
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
