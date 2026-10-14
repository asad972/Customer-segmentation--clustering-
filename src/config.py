"""Project-wide paths and constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

RAW_CSV = RAW_DIR / "online_retail_II.csv"
CLEAN_CSV = PROCESSED_DIR / "transactions_clean.csv"
FEATURES_CSV = PROCESSED_DIR / "customer_features.csv"
SEGMENTS_CSV = PROCESSED_DIR / "customer_segments.csv"
SEGMENT_SUMMARY_CSV = REPORTS_DIR / "segment_summary.csv"
CLEANING_LOG_MD = REPORTS_DIR / "cleaning_log.md"
METRICS_JSON = REPORTS_DIR / "metrics.json"

RANDOM_SEED = 42

# Candidate numbers of clusters evaluated by the elbow and silhouette methods.
K_RANGE = range(2, 11)
