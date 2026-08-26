"""
CashGuard AI — one-command bootstrap & demo runner.

Usage:
    python run.py                # generate data (if missing) + train (if missing) + serve
    python run.py --generate     # regenerate the synthetic dataset
    python run.py --train        # (re)train the model
    python run.py --serve        # start the FastAPI server (default port 8000)
    python run.py --demo         # force full pipeline: generate + train + serve
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import uvicorn

from backend.config import DATA_DIR, MODEL_PATH, SIMULATED_NOW

ROOT = Path(__file__).parent


def ensure_deps() -> None:
    """Friendly guard: point the user at requirements.txt if imports fail."""
    try:
        import fastapi  # noqa: F401
        import xgboost  # noqa: F401
    except ImportError:
        sys.exit(
            "Missing dependencies. Run:\n"
            "  pip install -r requirements.txt\n"
            "or (recommended) create a venv first."
        )


def run_script(script: str) -> None:
    print(f">> Running {script} ...")
    subprocess.run([sys.executable, script], check=True, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="CashGuard AI bootstrap")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--demo", action="store_true", help="force generate + train + serve")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    ensure_deps()

    db_exists = (DATA_DIR / "cashguard.db").exists()
    model_exists = MODEL_PATH.exists()

    want_generate = args.demo or args.generate or (not args.train and not args.serve and not db_exists)
    want_train = args.demo or args.train or (not args.generate and not args.serve and not model_exists)

    if want_generate:
        run_script("scripts/generate_data.py")
    if want_train:
        run_script("scripts/train_model.py")

    print(
        ">> Starting CashGuard AI server...\n"
        f"   Dashboard: http://localhost:{args.port}\n"
        f"   API docs : http://localhost:{args.port}/docs\n"
        f"   Simulated now: {SIMULATED_NOW or 'latest data timestamp (auto)'}"
    )
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=args.port, reload=False)


if __name__ == "__main__":
    main()