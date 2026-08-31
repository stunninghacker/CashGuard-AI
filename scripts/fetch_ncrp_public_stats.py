import csv
import json
import os
from pathlib import Path
import requests

def fetch_ncrp_public_stats(url: str = "https://ncrp.gov.in/annual_report_2022_23.csv") -> Path:
    """Download the public NCRP CSV report, parse it, and write a JSON file.
    The JSON contains a dict keyed by state, each mapping to a dict of
    category -> complaint count.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    # Assume CSV with headers: State,Category,Count
    rows = list(csv.DictReader(response.text.splitlines()))
    data = {}
    for r in rows:
        state = r["State"].strip()
        cat = r["Category"].strip()
        count = int(r["Count"].replace(",", ""))
        data.setdefault(state, {})[cat] = count
    out_path = Path(__file__).resolve().parents[1] / "data" / "real" / "ncrp_public_stats.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print(f"Saved NCRP stats to {out_path}")
    return out_path

if __name__ == "__main__":
    fetch_ncrp_public_stats()
