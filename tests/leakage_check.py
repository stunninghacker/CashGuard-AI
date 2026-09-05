"""Quick leakage check script - compute feature correlations with target."""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from scipy import stats
import json
import os

# Load existing metrics to understand the data
with open('artifacts/metrics.json') as f:
    metrics = json.load(f)

print("=== Per-feature AUC (from metrics.json) ===")
per_feature = metrics.get('per_feature_auc', {})
if per_feature:
    items = list(per_feature.items())
    items_sorted = sorted(items, key=lambda x: abs(per_feature[x[0]]), reverse=True)
    # Convert AUC to approximate point-biserial correlation
    # AUC = Phi(r / sqrt(2)), so r = Phi_inv(AUC) * sqrt(2)
    from scipy.stats import norm
    results = []
    for feat, auc in items_sorted[:30]:
        # Approximate point-biserial from AUC
        r_approx = norm.isf(1 - auc) * np.sqrt(2) if auc > 0.5 else -norm.isf(auc) * np.sqrt(2)
        # Actually, simpler: point-biserial r = 2*(AUC - 0.5) for a quick approx
        r_quick = 2 * (auc - 0.5)
        results.append((feat, auc, r_quick))
    for feat, auc, r in results:
        print(f"  {r:5.3f}  {auc:5.3f}  {feat}")
else:
    print("No per_feature_auc found")

# Now let's check what's in current_metrics.json
with open('artifacts/current_metrics.json') as f:
    cm = json.load(f)

print("\n=== current_headline_metrics ===")
print(json.dumps(cm['current_headline_metrics'], indent=2))

print("\n=== per_feature_auc top 15 by |AUC-0.5| ===")
items = list(per_feature.items())
items_sorted = sorted(items, key=lambda x: abs(per_feature[x[0]] - 0.5), reverse=True)
for k, v in items_sorted[:15]:
    r_quick = 2 * (v - 0.5)
    print(f"  {r_quick:5.3f}  {v:5.3f}  {k}")