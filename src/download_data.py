"""Download the UCI "Online Retail II" dataset into data/raw/.

The dataset is published by the UCI Machine Learning Repository as a zip file
containing a single Excel workbook with two sheets (2009-2010 and 2010-2011).
Reading ~1M rows from Excel is slow, so after downloading we also write a
combined CSV copy that the rest of the pipeline reads.

Usage:
    python -m src.download_data          # download only if missing
    python -m src.download_data --force  # re-download
"""

from __future__ import annotations

import argparse
import logging
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from src.config import RAW_CSV, RAW_DIR

DATASET_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
ZIP_PATH = RAW_DIR / "online_retail_ii.zip"
XLSX_NAME = "online_retail_II.xlsx"

logger = logging.getLogger(__name__)


def _download(url: str, dest: Path, max_retries: int = 10) -> None:
    """Stream ``url`` to ``dest``, resuming after dropped connections.

    The UCI server occasionally resets long downloads, so data is written to a
    ``.part`` file and each retry asks for the remaining bytes with an HTTP
    Range header. ``dest`` only appears once the download is complete.
    """
    part = dest.with_suffix(dest.suffix + ".part")
    logger.info("Downloading %s", url)
    for attempt in range(1, max_retries + 1):
        offset = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(url, stream=True, timeout=120, headers=headers) as resp:
                if resp.status_code == 416:  # nothing left to fetch
                    break
                resp.raise_for_status()
                # 200 means the server ignored the Range header: start over.
                mode = "ab" if resp.status_code == 206 else "wb"
                with open(part, mode) as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            break
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
            logger.warning("Attempt %d/%d interrupted (%s); resuming...", attempt, max_retries, exc)
            time.sleep(min(2 * attempt, 10))
    else:
        raise RuntimeError(f"Download failed after {max_retries} attempts: {url}")

    if not zipfile.is_zipfile(part):
        part.unlink()
        raise RuntimeError("Downloaded file is not a valid zip archive; please re-run.")
    part.replace(dest)
    logger.info("Saved %s (%.1f MB)", dest, dest.stat().st_size / 1e6)


def _excel_to_csv(xlsx_path: Path, csv_path: Path) -> None:
    """Read every sheet of the workbook and write one combined CSV."""
    logger.info("Converting %s to CSV (this takes a few minutes)...", xlsx_path.name)
    sheets = pd.read_excel(xlsx_path, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
    frames = []
    for name, sheet in sheets.items():
        logger.info("  sheet %-15s %9d rows", name, len(sheet))
        frames.append(sheet)
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(csv_path, index=False)
    logger.info("Wrote %s (%d rows)", csv_path, len(combined))


def download(force: bool = False) -> Path:
    """Ensure the raw CSV exists and return its path."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_CSV.exists() and not force:
        logger.info("Raw data already present at %s", RAW_CSV)
        return RAW_CSV

    xlsx_path = RAW_DIR / XLSX_NAME
    if force or not xlsx_path.exists():  # a manually downloaded workbook is used as-is
        have_valid_zip = ZIP_PATH.exists() and zipfile.is_zipfile(ZIP_PATH)
        if force or not have_valid_zip:
            _download(DATASET_URL, ZIP_PATH)
        with zipfile.ZipFile(ZIP_PATH) as zf:
            member = next(m for m in zf.namelist() if m.endswith(XLSX_NAME))
            with zf.open(member) as src, open(xlsx_path, "wb") as dst:
                dst.write(src.read())

    _excel_to_csv(xlsx_path, RAW_CSV)
    return RAW_CSV


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download even if the file exists")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    download(force=args.force)


if __name__ == "__main__":
    main()
