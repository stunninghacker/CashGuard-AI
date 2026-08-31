# validate_ncrp_vs_synthetic.py
"""Validate synthetic complaint generator against public NCRP stats.

Loads `data/real/ncrp_public_stats.json` as written by
`fetch_ncrp_public_stats.py` — a dict keyed by state, each mapping
`category -> complaint count` — aggregates counts per category across all
states, and compares the category distribution to the synthetic complaints in
`data/complaints.csv` (column `complaint_type`).

Prints a markdown table of synthetic % vs real % with the absolute difference;
validation passes when every difference is <= 8%.
"""

import json
import pathlib
import sys

import pandas as pd

DATA_ROOT = pathlib.Path(__file__).resolve().parents[1]
REAL_STATS_PATH = DATA_ROOT / "data" / "real" / "ncrp_public_stats.json"
SYNTHETIC_PATH = DATA_ROOT / "data" / "complaints.csv"

THRESHOLD = 8.0  # percent


def load_real_stats():
    if not REAL_STATS_PATH.exists():
        sys.stderr.write(f"[ERROR] {REAL_STATS_PATH} not found. Run fetch_ncrp_public_stats.py first.\n")
        sys.exit(1)
    with open(REAL_STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    counts: dict[str, int] = {}
    if isinstance(data, dict):
        # Format written by fetch_ncrp_public_stats.py: {state: {category: count}}
        for _state, cats in data.items():
            if not isinstance(cats, dict):
                continue
            for cat, n in cats.items():
                counts[str(cat).strip()] = counts.get(str(cat).strip(), 0) + int(n)
    elif isinstance(data, list):
        # Backward compat: list of rows with Category/Count columns
        for row in data:
            cat = str(row.get("Category") or row.get("category") or "").strip()
            n = row.get("Count", row.get("count", 0))
            if cat:
                counts[cat] = counts.get(cat, 0) + int(n)

    if not counts:
        sys.stderr.write("[ERROR] No category counts found in NCRP data.\n")
        sys.exit(1)

    total = sum(counts.values())
    return {cat: n / total * 100.0 for cat, n in counts.items()}


def load_synthetic_stats():
    if not SYNTHETIC_PATH.exists():
        sys.stderr.write(f"[ERROR] Synthetic complaints file {SYNTHETIC_PATH} missing.\n")
        sys.exit(1)
    df = pd.read_csv(SYNTHETIC_PATH)
    col = "complaint_type" if "complaint_type" in df.columns else (
        "category" if "category" in df.columns else None
    )
    if col is None:
        sys.stderr.write("[ERROR] Synthetic CSV lacks 'complaint_type' column.\n")
        sys.exit(1)
    pct = df[col].value_counts(normalize=True) * 100
    return pct.to_dict()


def main():
    real = load_real_stats()
    synth = load_synthetic_stats()
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
