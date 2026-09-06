#!/usr/bin/env python3
"""CashGuard AI — Performance Benchmark Script
Measures API response times, payload sizes, and frontend characteristics.
Run with: python scripts/performance_benchmark.py
"""
import json
import time
import statistics
import urllib.request
import urllib.error
import os
import sys

BASE_URL = os.environ.get("CG_URL", "http://localhost:8000")
ITERATIONS = 3
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "artifacts", "performance_baseline.json")


def login(username="i4c.admin", password="I4cAdmin!1"):
    data = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(f"{BASE_URL}/auth/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def measure_endpoint(token, method, path, iterations=ITERATIONS):
    """Measure a single endpoint over multiple iterations."""
    headers = {"Authorization": f"Bearer {token}"}
    times = []
    size = 0
    for _ in range(iterations):
        start = time.perf_counter()
        req = urllib.request.Request(f"{BASE_URL}{path}", method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
                size = len(body)
        except Exception as e:
            return {"error": str(e), "ms": -1, "bytes": 0}
    return {
        "ms_median": round(statistics.median(times)),
        "ms_min": round(min(times)),
        "ms_max": round(max(times)),
        "bytes": size,
        "kb": round(size / 1024, 1),
    }


def measure_file_sizes():
    """Measure frontend asset sizes."""
    base = os.path.join(os.path.dirname(__file__), "..", "frontend")
    files = {
        "index.html": os.path.join(base, "index.html"),
        "style.css": os.path.join(base, "style.css"),
        "app.js": os.path.join(base, "app.js"),
        "leaflet.js": os.path.join(base, "vendor", "leaflet", "leaflet.js"),
        "leaflet.css": os.path.join(base, "vendor", "leaflet", "leaflet.css"),
    }
    result = {}
    total = 0
    for name, path in files.items():
        if os.path.exists(path):
            sz = os.path.getsize(path)
            result[name] = {"bytes": sz, "kb": round(sz / 1024, 1)}
            total += sz
    result["_total"] = {"bytes": total, "kb": round(total / 1024, 1)}
    return result


def count_dom_nodes():
    """Estimate DOM nodes from HTML."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if not os.path.exists(html_path):
        return -1
    with open(html_path) as f:
        html = f.read()
    import re
    tags = re.findall(r'<(div|span|table|thead|tbody|tr|th|td|button|select|option|input|label|nav|aside|header|footer|section|a |h[1-6]|p |img|path|svg)', html)
    return len(tags)


def run_benchmark():
    print(f"CashGuard AI Performance Benchmark")
    print(f"Target: {BASE_URL}")
    print(f"Iterations: {ITERATIONS}")
    print("=" * 60)

    # File sizes
    print("\n[1/3] Frontend Asset Sizes")
    files = measure_file_sizes()
    for name, info in files.items():
        if name.startswith("_"):
            print(f"  TOTAL: {info['kb']}KB")
        else:
            print(f"  {name}: {info['kb']}KB")

    # DOM nodes
    print("\n[2/3] DOM Analysis")
    dom = count_dom_nodes()
    print(f"  Estimated DOM nodes: {dom}")

    # API endpoints
    print("\n[3/3] API Response Times")
    token = login()
    print(f"  Authenticated as i4c.admin")

    endpoints = [
        ("GET", "/risk-scores", "Risk scores (900 ATMs)"),
        ("GET", "/alerts?limit=200", "Alerts (200)"),
        ("GET", "/stats/summary", "Stats summary"),
        ("GET", "/hotspots", "Hotspot ATMs"),
        ("GET", "/horizons", "Horizons"),
        ("GET", "/recovery/recommendations", "Recovery queue"),
        ("GET", "/recovery/funnel", "Recovery funnel"),
        ("GET", "/mule-graph/terminal-nodes", "Mule terminal nodes"),
        ("GET", "/drift/status", "Drift status"),
        ("GET", "/graph/mule-network", "Mule network graph"),
        ("GET", "/ledger/verify", "Ledger verify"),
        ("GET", "/ledger", "Ledger (full)"),
        ("GET", "/train/status", "Train status"),
        ("GET", "/mock-i4c-inbox", "I4C inbox"),
        ("GET", "/alerts/handoffs/list", "Handoffs"),
        ("GET", "/complaints?limit=20000", "Complaints (20K)"),
        ("GET", "/atms?limit=5000", "ATMs (5K)"),
        ("GET", "/threshold-explorer", "Threshold explorer"),
        ("GET", "/atms/banks", "Bank list"),
        ("GET", "/blockchain", "Blockchain"),
        ("GET", "/i18n/locales", "i18n locales"),
    ]

    api_results = {}
    for method, path, desc in endpoints:
        result = measure_endpoint(token, method, path)
        api_results[path] = result
        status = f"{result['ms_median']}ms" if result.get("ms_median", -1) > 0 else result.get("error", "ERR")
        print(f"  {desc:30s} {path:45s} {status:10s} {result.get('kb', 0):>8.1f}KB")

    # Summary
    total_api_time = sum(r["ms_median"] for r in api_results.values() if r.get("ms_median", -1) > 0)
    total_api_bytes = sum(r["bytes"] for r in api_results.values() if r.get("bytes", 0) > 0)

    print("\n" + "=" * 60)
    print(f"SUMMARY")
    print(f"  Frontend assets: {files['_total']['kb']}KB")
    print(f"  DOM nodes: {dom}")
    print(f"  API endpoints measured: {len(endpoints)}")
    print(f"  Total API sequential time: {total_api_time}ms")
    print(f"  Total API payload: {round(total_api_bytes/1024, 1)}KB")

    # Save baseline
    baseline = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": f"Python {sys.version.split()[0]}, local server",
        "iterations": ITERATIONS,
        "frontend_assets": files,
        "dom_nodes": dom,
        "api_results": api_results,
        "summary": {
            "total_api_time_ms": total_api_time,
            "total_api_payload_bytes": total_api_bytes,
            "total_api_payload_kb": round(total_api_bytes / 1024, 1),
        },
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"\nBaseline saved to: {OUTPUT}")


if __name__ == "__main__":
    run_benchmark()
