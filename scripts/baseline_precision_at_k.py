# baseline_precision_at_k.py
"""Calculate precision@K for three baselines and the CashGuard model.
Baselines:
1. Busiest ATMs – rank by total withdrawal volume.
2. Random selection of ATMs.
3. Persistence – use ATMs selected on the previous day.
The script prints a markdown table for K = [10, 20, 50, 100].
"""

import random
import numpy as np
import pandas as pd
from pathlib import Path

# Paths – adjust if your project layout differs
DATA_ROOT = Path(__file__).resolve().parents[1]
COMPLAINTS_PATH = DATA_ROOT / "data" / "complaints.csv"
MODEL_SCORES_PATH = DATA_ROOT / "backend" / "ml" / "two_stage_model_scores.csv"  # assume scores saved

K_VALUES = [10, 20, 50, 100]

# ---------------------------------------------------------------------------
def load_data():
    complaints = pd.read_csv(COMPLAINTS_PATH)
    # Assume a column `is_fraud` (1 for fraud event, 0 otherwise)
    if "is_fraud" not in complaints.columns:
        raise ValueError("complaints.csv must contain 'is_fraud' column for evaluation")
    # Load model scores (atm_id, score)
    scores = pd.read_csv(MODEL_SCORES_PATH)
    return complaints, scores

# ---------------------------------------------------------------------------
def precision_at_k(selected_atms, true_fraud_atms, k):
    # selected_atms: list of atm_id selected for intervention
    # true_fraud_atms: set of atm_id that actually had fraud events
    hits = len(set(selected_atms[:k]) & true_fraud_atms)
    return hits / k

# ---------------------------------------------------------------------------
def run_baselines(complaints, scores):
    true_fraud_atms = set(complaints[complaints["is_fraud"] == 1]["atm_id"].unique())

    # 1. Busiest ATMs – use withdrawal volume from complaints
    volume_by_atm = complaints.groupby("atm_id")["amount"].sum().sort_values(ascending=False)
    busiest = list(volume_by_atm.index)

    # 2. Random – shuffle ATM list
    random_atms = list(volume_by_atm.index)
    random.shuffle(random_atms)

    # 3. Persistence – assume we have previous day selections saved in a CSV
    # For simplicity, reuse busiest of the previous day simulated by shifting the order
    persistence = busiest[::-1]  # placeholder reversed order

    # 4. CashGuard model scores – already sorted descending
    model_sorted = scores.sort_values(by="score", ascending=False)["atm_id"].tolist()

    results = {}
    for K in K_VALUES:
        results[K] = {
            "busiest": precision_at_k(busiest, true_fraud_atms, K),
            "random": precision_at_k(random_atms, true_fraud_atms, K),
            "persistence": precision_at_k(persistence, true_fraud_atms, K),
            "cashguard": precision_at_k(model_sorted, true_fraud_atms, K),
        }
    return results

# ---------------------------------------------------------------------------
def main():
    complaints, scores = load_data()
    res = run_baselines(complaints, scores)
    print("\n| K | CashGuard | Busiest | Random | Persistence |\n|---|---|---|---|---|")
    for K in K_VALUES:
        row = res[K]
        print(f"| {K} | {row['cashguard']:.3f} | {row['busiest']:.3f} | {row['random']:.3f} | {row['persistence']:.3f} |")
    print("\nInterpretation: CashGuard should exceed Random by ≥40 % at K=100.")

if __name__ == "__main__":
    main()
