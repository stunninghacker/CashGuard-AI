"""Real-world calibration pass: compares generator parameters against PUBLIC,
citable datasets (ATM density, complaint volumes, fraud statistics). Where a
public figure can calibrate a parameter it is marked 'adjustable'; where no
public benchmark exists (per-ATM fraud withdrawal rates) the gap is stated
honestly. This is NOT real NCRP/bank data — it is the honest use of the best
publicly available analog.

Run: python scripts/real_world_calibration.py
Out: artifacts/deep_eval/real_world_calibration.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.data.synthetic_data import load_calibration_config  # noqa: E402

# Public figures: named reports, cautious ranges, dates. Every figure below is
# from an official/authoritative public report; verify the exact number before
# quoting in production material (the repo's standard discipline).
PUBLIC_BENCHMARKS = [
    {
        "id": "atm_total_india",
        "name": "Total ATMs in India",
        "source": "RBI — annual statistics on ATM terminals (Trend & Progress / Banking Statistics)",
        "url": "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Trend%20and%20Progress%20of%20Banking%20in%20India",
        "public_figure": "~2.2\u20132.6 lakh ATM terminals (2023\u201324, RBI reports)",
        "generator_param": "dataset.n_atms_per_city x 5 cities",
        "generator_value": "900 ATMs",
        "gap_class": "scale_shift",
        "note": "The generator is a downscaled demo (900 fictional ATMs vs ~2.4 lakh real). The ratio ATMs/city and heavy-tail traffic weights are directional; per-capita ATM density is NOT asserted as real.",
    },
    {
        "id": "complaints_per_day",
        "name": "NCRP cybercrime complaint volume",
        "source": "I4C/MHA public statements on NCRP intake (media-reported ~8,000 complaints/day)",
        "url": "https://i4c.mha.gov.in",
        "public_figure": "~8,000 complaints/day (public I4C statements)",
        "generator_param": "dataset.n_complaints over 6 months",
        "generator_value": "12,426 complaints (~69/day)",
        "gap_class": "scale_shift",
        "note": "Demo-scale downshift ~116x. The final-wave concentration and complaint-type mix are directional only. The load test (LOAD_TEST.md) is sized at the real 8,000/day figure.",
    },
    {
        "id": "upi_fraud_share",
        "name": "UPI payment fraud share (directional)",
        "source": "RBI Annual Report / IDRBT UPI fraud data (public)",
        "url": "https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx",
        "public_figure": "UPI fraud counts/amounts are a small fraction of UPI transaction volume (per RBI/IDRBT public reports)",
        "generator_param": "dataset.fraud_share",
        "generator_value": "0.10 of withdrawals",
        "gap_class": "no_public_benchmark",
        "note": "No public per-ATM fraud-withdrawal rate exists. fraud_share is a synthetic label density, explicitly not a real-world rate (CALIBRATION_NOTES.md). Direction: real fraud is a small share of transactions \u2014 consistent.",
    },
    {
        "id": "mule_behaviour",
        "name": "Mule account behavioural characteristics",
        "source": "IBA / I4C Suspect Registry direction (already cited in CALIBRATION_NOTES.md)",
        "url": "",
        "public_figure": "Directional: mule accounts show velocity/counterparty/spike patterns",
        "generator_param": "behaviour.*",
        "generator_value": "velocity ~30k INR/h mean, burst chunking",
        "gap_class": "consistent_direction",
        "note": "Exact coefficients are tunable assumptions; direction verified (see CALIBRATION_NOTES.md).",
    },
    {
        "id": "fraud_to_cashout_latency",
        "name": "Fraud-to-cash-out latency (directional)",
        "source": "RBI 2026 lag-credit hold direction (cited in CALIBRATION_NOTES.md)",
        "url": "",
        "public_figure": "Regulatory direction: an interception window is being created; no public mean latency",
        "generator_param": "timing.fraud_to_cashout_mean_hours",
        "generator_value": "18h (right-skewed)",
        "gap_class": "no_public_benchmark",
        "note": "18h is an assumption; the 24h forecast horizon is justified by the interception-window direction only.",
    },
]

OUT = {
    "label": "PUBLIC-BENCHMARK CALIBRATION PASS \u2014 not real NCRP/bank data",
    "method": "compares generator parameters against official/public reports; where no public benchmark exists the gap is stated, not filled",
    "benchmarks": PUBLIC_BENCHMARKS,
    "actionable_adjustments": [
        "None made: all comparisons are directional or scale-shifted. Adjusting coefficients without a public per-ATM benchmark would be fabrication, not calibration."
    ],
    "remaining_gap": "Authorized NCRP/CFCFRMS/bank access (REAL_DATA_GAP.md) is required for true recalibration \u2014 the protocol in REAL_DATA_VALIDATION_PROTOCOL.md is the mechanism.",
    "verification_before_quoting": "Exact figures must be confirmed against the cited reports before any production/competition material uses them.",
}


def main():
    cfg = load_calibration_config()
    for b in PUBLIC_BENCHMARKS:
        print(f"- {b['id']:<28} {b['gap_class']:<22} public: {b['public_figure'][:44]}...")
    (ROOT / "artifacts" / "deep_eval" / "real_world_calibration.json").write_text(
        json.dumps(OUT, indent=2), encoding="utf-8")
    print("saved: artifacts/deep_eval/real_world_calibration.json")
    print("adjustments:", OUT["actionable_adjustments"][0])


if __name__ == "__main__":
    main()