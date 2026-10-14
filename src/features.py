"""Build one row of behavioural features per customer.

Features
--------
Recency          days since the customer's last purchase (lower = more recent)
Frequency        number of distinct invoices (orders)
Monetary         total revenue, £
AvgOrderValue    Monetary / Frequency, £
DistinctProducts number of different stock codes bought
TenureDays       days since the customer's first purchase

All are measured relative to a snapshot date one day after the last invoice
in the data. Skewed features are log-transformed, then everything is
standardised so that no single feature dominates the distance metric.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.config import FEATURES_CSV

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "Recency", "Frequency", "Monetary", "AvgOrderValue", "DistinctProducts", "TenureDays",
]
SKEW_THRESHOLD = 1.0  # |skewness| above this triggers a log1p transform


def snapshot_date(transactions: pd.DataFrame) -> pd.Timestamp:
    """Reference date for recency/tenure: the day after the last invoice."""
    return transactions["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)


def build_customer_features(transactions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate clean transactions into one feature row per customer."""
    snap = snapshot_date(transactions)
    grouped = transactions.groupby("CustomerID")
    features = pd.DataFrame({
        "Recency": (snap - grouped["InvoiceDate"].max()).dt.days,
        "Frequency": grouped["Invoice"].nunique(),
        "Monetary": grouped["Revenue"].sum(),
        "DistinctProducts": grouped["StockCode"].nunique(),
        "TenureDays": (snap - grouped["InvoiceDate"].min()).dt.days,
    })
    features["AvgOrderValue"] = features["Monetary"] / features["Frequency"]
    features = features[FEATURE_COLUMNS]

    if features.isna().any().any():
        raise ValueError("Customer features contain missing values")
    if (features[["Frequency", "Monetary", "DistinctProducts"]] <= 0).any().any():
        raise ValueError("Frequency, Monetary and DistinctProducts must be positive")
    return features


def transform_features(features: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict]:
    """Log-transform skewed features and standardise all of them.

    Returns the scaled matrix (same index/columns), the list of columns that
    were log-transformed, and the skewness before/after for reporting.
    """
    skew_before = features.skew()
    log_cols = [c for c in FEATURE_COLUMNS if abs(skew_before[c]) > SKEW_THRESHOLD]
    transformed = features.copy().astype(float)
    transformed[log_cols] = np.log1p(transformed[log_cols])
    skew_after = transformed.skew()

    scaled = pd.DataFrame(
        StandardScaler().fit_transform(transformed),
        index=features.index, columns=FEATURE_COLUMNS,
    )
    skew_report = {
        c: {"before": round(float(skew_before[c]), 2), "after": round(float(skew_after[c]), 2)}
        for c in FEATURE_COLUMNS
    }
    logger.info("Log-transformed: %s", ", ".join(log_cols))
    return scaled, log_cols, skew_report


def run(transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    """Build, save and transform customer features."""
    features = build_customer_features(transactions)
    FEATURES_CSV.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURES_CSV)
    logger.info("Built features for %d customers -> %s", len(features), FEATURES_CSV.name)
    scaled, log_cols, skew_report = transform_features(features)
    return features, scaled, log_cols, skew_report
