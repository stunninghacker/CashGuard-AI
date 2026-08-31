# fetch_kaggle_cybercrime.py
"""Download a public Kaggle cyber‑crime dataset for India.
The script uses the Kaggle API (`kaggle` package). You must have a Kaggle
API token in `~/.kaggle/kaggle.json` (or set the environment variables
`KAGGLE_USERNAME` and `KAGGLE_KEY`).
The chosen dataset is `thedevilsgarden/cybercrime-india` – replace with any
public dataset you prefer.
The downloaded CSV(s) are extracted to `data/real/kaggle_cybercrime/`.
"""

import os
import pathlib
import sys
import zipfile

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
except ImportError:
    sys.stderr.write("[ERROR] kaggle package not installed. Install with 'pip install kaggle'.\n")
    sys.exit(1)

DATA_ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = DATA_ROOT / "data" / "real" / "kaggle_cybercrime"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATASET = os.getenv("KAGGLE_DATASET", "thedevilsgarden/cybercrime-india")


def main():
    api = KaggleApi()
    api.authenticate()
    # Download as zip to a temporary location
    zip_path = OUT_DIR / "dataset.zip"
    api.dataset_download_files(DATASET, path=str(OUT_DIR), unzip=False, quiet=False)
    # Kaggle CLI saves as <dataset>.zip, locate it
    zip_file = next(OUT_DIR.glob("*.zip"), None)
    if not zip_file:
        sys.stderr.write("[ERROR] Failed to locate downloaded zip file.\n")
        sys.exit(1)
    # Extract
    with zipfile.ZipFile(zip_file, 'r') as zf:
        zf.extractall(OUT_DIR)
    print(f"[INFO] Extracted Kaggle dataset to {OUT_DIR}")
    # Optionally delete zip
    try:
        zip_file.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    main()
