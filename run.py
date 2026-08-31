#!/usr/bin/env python3
"""
CashGuard AI — Hardened Bootstrap Runner
Handles common Windows/Python 3.11 startup failure modes.

Usage:
    python run.py                # generate data (if missing) + train (if missing) + serve
    python run.py --generate     # force-regenerate the synthetic dataset, then serve
    python run.py --train        # force-retrain the model, then serve
    python run.py --serve        # skip generate/train, just start the server
    python run.py --demo         # force full pipeline: generate + train + serve
    python run.py --port 8000    # choose the main server port (default 8000)

Env overrides: PORT, HOST, CFCFRMS_PORT, DEMO_MODE, SKIP_GENERATE, SKIP_TRAIN.
"""

import argparse
import os
import sys
import time
import socket
import logging
import asyncio
import subprocess
from pathlib import Path

# ── Windows asyncio fix ──────────────────────────────────────────────────────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── Windows console UTF-8 fix ────────────────────────────────────────────────
# The Windows console defaults to code page cp1252 (or cp437), which cannot
# encode the box-drawing characters (═ ─ ╔) used in the log banners, causing
# spurious "Logging error ... UnicodeEncodeError" tracebacks on every startup.
# Reconfigure stdio to UTF-8 so banners render cleanly without crashing the
# handler. Only affects this process's console output, not file handlers.
if sys.platform == "win32":
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

# ── Path setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "bootstrap.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("cashguard.bootstrap")

# ── JWT secure-boot opt-in ───────────────────────────────────────────────────
# backend.api.main refuses to boot with the public default JWT_SECRET unless
# the demo opt-in is set. A bootstrap runner for the hackathon demo opts in
# automatically; exporting a real JWT_SECRET always takes precedence.
if not os.environ.get("JWT_SECRET"):
    os.environ["ALLOW_INSECURE_DEFAULT_JWT"] = "1"
    log.info("JWT_SECRET not set — demo opt-in ALLOW_INSECURE_DEFAULT_JWT=1 "
             "(set a strong JWT_SECRET for any real deployment)")

# ── Configuration ─────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8000))
CFCFRMS_PORT = int(os.environ.get("CFCFRMS_PORT", 8001))
HOST = os.environ.get("HOST", "0.0.0.0")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
SKIP_GENERATE = os.environ.get("SKIP_GENERATE", "false").lower() == "true"
SKIP_TRAIN = os.environ.get("SKIP_TRAIN", "false").lower() == "true"


def check_port_free(port: int) -> bool:
    """Returns True if port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        return result != 0


def free_port(port: int):
    """Kill whatever is using the port (Windows-safe)."""
    log.warning(f"Port {port} is in use. Attempting to free it...")
    if sys.platform == "win32":
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if parts and parts[-1].isdigit():
                pid = parts[-1]
                subprocess.run(f"taskkill /PID {pid} /F", shell=True, capture_output=True)
                log.info(f"Killed PID {pid} on port {port}")
    else:
        subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
    time.sleep(2)


def verify_dependencies():
    """Check all critical imports before attempting startup."""
    log.info("Verifying dependencies")
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "xgboost": "xgboost",
        "sklearn": "scikit-learn",
        "pandas": "pandas",
        "numpy": "numpy",
        "joblib": "joblib",
        "sqlalchemy": "sqlalchemy",
        "jose": "python-jose[cryptography]",
        "passlib": "passlib[bcrypt]",
        "apscheduler": "apscheduler",
    }
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            log.info(f"  [OK] {module}")
        except ImportError:
            log.error(f"  [MISSING] {module} – install with: pip install {package}")
            missing.append(package)
    if missing:
        log.error(f"Missing packages: {missing}")
        log.error("Run: pip install " + " ".join(missing))
        sys.exit(1)
    log.info("  All dependencies verified [OK]")


def generate_data(force: bool = False):
    """Generate the synthetic dataset (skipped when the DB already exists)."""
    log.info("── Stage 1: Synthetic data ─────────────────────────────")
    if SKIP_GENERATE:
        log.info("  SKIP_GENERATE=true — skipping generation.")
        return
    db_path = ROOT / "data" / "cashguard.db"
    if db_path.exists() and not force:
        log.info("  Existing database found. Skipping generation.")
        log.info("  Use --generate (or --demo) to force regeneration.")
        return
    script = ROOT / "scripts" / "generate_data.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    if result.returncode != 0:
        log.error("Data generation FAILED. Check output above.")
        sys.exit(1)
    log.info("  Data generation complete ✓")


def train_model(force: bool = False):
    """Train the model (skipped when model.joblib already exists)."""
    log.info("── Stage 2: Model training ─────────────────────────────")
    if SKIP_TRAIN:
        log.info("  SKIP_TRAIN=true — skipping training.")
        return
    model_path = ROOT / "artifacts" / "model.joblib"
    if model_path.exists() and not force:
        log.info("  Existing model found. Skipping training.")
        log.info("  Use --train (or --demo) to force retraining.")
        return
    script = ROOT / "scripts" / "train_model.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    if result.returncode != 0:
        log.error("Model training FAILED. Check output above.")
        sys.exit(1)
    log.info("  Model training complete ✓")


def cache_demo():
    """Pre-compute demo mode cache."""
    log.info("── Stage 3: Demo cache ─────────────────────────────────")
    script = ROOT / "scripts" / "cache_demo_mode.py"
    if script.exists():
        result = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
        if result.returncode != 0:
            log.warning("Demo cache generation failed — continuing without it.")
    else:
        log.warning("  cache_demo_mode.py not found — skipping.")


def start_cfcfrms_server():
    """Start mock CFCFRMS server on port 8001 (optional component)."""
    server_path = ROOT / "backend" / "mock_cfcfrms" / "server.py"
    if not server_path.exists():
        log.info("── Stage 4: Mock CFCFRMS server not present — skipping ─")
        return None
    log.info("── Stage 4: Starting mock CFCFRMS server ───────────────")
    if not check_port_free(CFCFRMS_PORT):
        free_port(CFCFRMS_PORT)
    proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "backend.mock_cfcfrms.server:app",
        "--host", HOST,
        "--port", str(CFCFRMS_PORT),
        "--log-level", "warning",
    ], cwd=str(ROOT))
    time.sleep(2)
    log.info(f"  Mock CFCFRMS server running on port {CFCFRMS_PORT} ✓")
    return proc


def start_main_server(port: int):
    """Start the main FastAPI server (blocking)."""
    log.info("── Stage 5: Starting CashGuard AI server ───────────────")
    if not check_port_free(port):
        free_port(port)
        if not check_port_free(port):
            log.error(f"Port {port} still in use after kill attempt.")
            log.error(f"Manually run: netstat -ano | findstr :{port}")
            sys.exit(1)
    import uvicorn
    config = uvicorn.Config(
        "backend.api.main:app",
        host=HOST,
        port=port,
        log_level="info",
        reload=False,
        workers=1,
    )
    server = uvicorn.Server(config)
    cfcfrms_line = f"|  CFCFRMS Mock:    http://localhost:{CFCFRMS_PORT}            |\n"
    log.info(f"\n+{'='*70}+\n|         CashGuard AI — Started Successfully                  |\n+{'='*70}+\n|  Main Dashboard:  http://localhost:{port}                    |\n|  API Docs:        http://localhost:{port}/docs               |\n|  Health Check:    http://localhost:{port}/health             |\n{cfcfrms_line}+{'='*70}+\n|  Demo Credentials: see docs/DEMO_CREDENTIALS.md             |\n|  DEMO_MODE: {str(DEMO_MODE).upper():<49}|\n+{'='*70}+\n")
    server.run()


def main():
    parser = argparse.ArgumentParser(description="CashGuard AI bootstrap")
    parser.add_argument("--generate", action="store_true", help="force-regenerate the dataset")
    parser.add_argument("--train", action="store_true", help="force-retrain the model")
    parser.add_argument("--serve", action="store_true", help="skip generate/train, just serve")
    parser.add_argument("--demo", action="store_true", help="force generate + train + serve")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    log.info("═══ CashGuard AI Bootstrap Starting ═══════════════════")
    verify_dependencies()

    if not args.serve:
        generate_data(force=args.generate or args.demo)
        train_model(force=args.train or args.demo)
    else:
        log.info("  --serve: skipping generate/train stages.")
    cache_demo()
    cfcfrms_proc = start_cfcfrms_server()
    try:
        start_main_server(args.port)
    finally:
        if cfcfrms_proc:
            cfcfrms_proc.terminate()
            log.info("Mock CFCFRMS server stopped.")

if __name__ == "__main__":
    main()
