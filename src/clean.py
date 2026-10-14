"""Clean the raw Online Retail II transactions.

Every step records how many rows it removed (and how much revenue that
represented) so the decisions are auditable in ``reports/cleaning_log.md``.
Validation checks run on both the raw input and the cleaned output and raise
``DataValidationError`` if an assumption the rest of the pipeline relies on
is broken.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import pandas as pd

from src.config import CLEAN_CSV, CLEANING_LOG_MD, RAW_CSV

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "Invoice", "StockCode", "Description", "Quantity",
    "InvoiceDate", "Price", "Customer ID", "Country",
]
MIN_RAW_ROWS = 1_000_000  # the published dataset has ~1.07M rows
DATE_RANGE = (pd.Timestamp("2009-12-01"), pd.Timestamp("2011-12-31"))

# Regular products have a 5-digit stock code, optionally followed by letters
# for variants (e.g. "85123A"). The one genuine product with a different
# format is whitelisted; everything else (POST, M, C2, ADJUST, ...) is a fee,
# adjustment or test code.
PRODUCT_CODE_PATTERN = re.compile(r"^\d{5}[A-Za-z]*$")
PRODUCT_CODE_EXCEPTIONS = {"SP1002"}  # "KID'S CHALKBOARD/EASEL"


class DataValidationError(Exception):
    """Raised when the data violates an assumption of the pipeline."""


@dataclass
class CleaningLog:
    """Collects one entry per cleaning step for the markdown report."""

    steps: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def record(self, step: str, before: pd.DataFrame, after: pd.DataFrame, reason: str) -> None:
        """Log the rows removed between ``before`` and ``after``."""
        removed = len(before) - len(after)
        self.steps.append(
            {"step": step, "rows_before": len(before), "rows_removed": removed,
             "rows_after": len(after), "reason": reason}
        )
        logger.info("%-40s removed %8d rows -> %8d", step, removed, len(after))

    def to_markdown(self, raw_rows: int, clean: pd.DataFrame) -> str:
        """Render the log as a markdown document."""
        lines = [
            "# Data cleaning log",
            "",
            "_Generated automatically by `src/clean.py`; do not edit by hand._",
            "",
            f"- Raw rows: **{raw_rows:,}**",
            f"- Clean rows: **{len(clean):,}** ({len(clean) / raw_rows:.1%} of raw)",
            f"- Customers: **{clean['CustomerID'].nunique():,}**",
            f"- Invoices: **{clean['Invoice'].nunique():,}**",
            f"- Products: **{clean['StockCode'].nunique():,}**",
            f"- Period: **{clean['InvoiceDate'].min():%Y-%m-%d}** to "
            f"**{clean['InvoiceDate'].max():%Y-%m-%d}**",
            f"- Revenue (clean): **£{clean['Revenue'].sum():,.0f}**",
            "",
            "## Steps",
            "",
            "| # | Step | Rows before | Rows removed | Rows after | Why |",
            "|---|------|------------:|-------------:|-----------:|-----|",
        ]
        for i, s in enumerate(self.steps, 1):
            lines.append(
                f"| {i} | {s['step']} | {s['rows_before']:,} | {s['rows_removed']:,} | "
                f"{s['rows_after']:,} | {s['reason']} |"
            )
        if self.notes:
            lines += ["", "## Notes", ""] + [f"- {n}" for n in self.notes]
        lines += ["", "## Validation checks passed", ""]
        lines += [f"- {c}" for c in VALIDATION_CHECKS_DESCRIPTION]
        return "\n".join(lines) + "\n"


VALIDATION_CHECKS_DESCRIPTION = [
    "Raw file has the expected 8 columns and at least 1,000,000 rows",
    "No missing Customer IDs",
    "No cancellation invoices (prefix 'C') remain",
    "All quantities and prices are strictly positive",
    "No exact duplicate rows",
    "Only product stock codes remain",
    f"All invoice dates fall within {DATE_RANGE[0]:%Y-%m-%d} to {DATE_RANGE[1]:%Y-%m-%d}",
    "Revenue equals Quantity x Price for every row",
    "Each invoice belongs to exactly one customer",
]


def _check(condition: bool, message: str) -> None:
    """Raise ``DataValidationError`` with ``message`` if ``condition`` is false."""
    if not condition:
        raise DataValidationError(message)


def validate_raw(df: pd.DataFrame) -> None:
    """Fail loudly if the raw file does not look like Online Retail II."""
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    _check(not missing, f"Raw data is missing columns: {sorted(missing)}")
    _check(len(df) >= MIN_RAW_ROWS,
           f"Raw data has only {len(df):,} rows; expected at least {MIN_RAW_ROWS:,}. "
           "Was the download truncated?")


def validate_clean(df: pd.DataFrame) -> None:
    """Fail loudly if the cleaned data breaks any downstream assumption."""
    _check(df["CustomerID"].notna().all(), "Missing Customer IDs remain")
    _check(not df["Invoice"].str.startswith("C").any(), "Cancellation invoices remain")
    _check((df["Quantity"] > 0).all(), "Non-positive quantities remain")
    _check((df["Price"] > 0).all(), "Non-positive prices remain")
    _check(not df.duplicated().any(), "Exact duplicate rows remain")
    _check(df["StockCode"].map(is_product_code).all(), "Non-product stock codes remain")
    _check(df["InvoiceDate"].between(*DATE_RANGE).all(), "Invoice dates outside the expected range")
    _check(((df["Quantity"] * df["Price"] - df["Revenue"]).abs() < 1e-6).all(),
           "Revenue does not equal Quantity x Price")
    customers_per_invoice = df.groupby("Invoice")["CustomerID"].nunique()
    _check((customers_per_invoice == 1).all(), "Some invoices belong to more than one customer")


def is_product_code(code: str) -> bool:
    """Return True if ``code`` identifies a physical product."""
    return bool(PRODUCT_CODE_PATTERN.match(code)) or code in PRODUCT_CODE_EXCEPTIONS


def load_raw() -> pd.DataFrame:
    """Read the raw CSV produced by ``src.download_data``."""
    if not RAW_CSV.exists():
        raise FileNotFoundError(
            f"{RAW_CSV} not found. Run `python -m src.download_data` first."
        )
    return pd.read_csv(
        RAW_CSV,
        dtype={"Invoice": str, "StockCode": str, "Description": str, "Country": str},
        parse_dates=["InvoiceDate"],
    )


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningLog]:
    """Apply every cleaning step and return the clean data plus its log."""
    log = CleaningLog()
    df = raw.copy()
    df["Invoice"] = df["Invoice"].str.strip()
    df["StockCode"] = df["StockCode"].str.strip().str.upper()

    before = df
    df = df[df["Customer ID"].notna()]
    log.record("Missing Customer ID", before, df,
               "Purchases cannot be attributed to a customer, so they cannot be segmented.")
    df = df.assign(CustomerID=df["Customer ID"].astype(int)).drop(columns="Customer ID")

    before = df
    df = df.drop_duplicates()
    log.record("Exact duplicate rows", before, df,
               "Identical lines (same invoice, product, quantity, price, time) are data-entry "
               "or export duplicates, including the overlap between the two Excel sheets.")

    is_cancel = df["Invoice"].str.startswith("C")
    cancelled = df[is_cancel]
    log.notes.append(
        f"Cancellations: {cancelled['Invoice'].nunique():,} cancellation invoices from "
        f"{cancelled['CustomerID'].nunique():,} customers, worth "
        f"£{(-cancelled['Quantity'] * cancelled['Price']).sum():,.0f}. They are excluded "
        "rather than netted against original orders because most originals cannot be "
        "matched one-to-one (many pre-date the dataset window)."
    )
    before = df
    df = df[~is_cancel]
    log.record("Cancellation invoices (prefix 'C')", before, df,
               "Returns/cancellations are not purchases; RFM should reflect what customers bought.")

    before = df
    df = df[df["Quantity"] > 0]
    log.record("Non-positive quantity", before, df,
               "Stock adjustments (damaged, lost, etc.) that are not customer purchases.")

    before = df
    df = df[df["Price"] > 0]
    log.record("Zero or negative price", before, df,
               "Free samples, internal adjustments and bad-debt write-offs carry no revenue.")

    non_product = ~df["StockCode"].map(is_product_code)
    removed_codes = (
        df[non_product].groupby("StockCode")
        .agg(rows=("Invoice", "size"), description=("Description", "first"))
        .sort_values("rows", ascending=False)
    )
    log.notes.append(
        "Non-product stock codes removed: "
        + ", ".join(f"`{c}` ({str(r.description).strip()}, {r.rows:,} rows)"
                    for c, r in removed_codes.iterrows())
    )
    before = df
    df = df[~non_product]
    log.record("Non-product stock codes", before, df,
               "Postage, carriage, manual adjustments, discounts, bank charges and test codes "
               "are not products and would distort spend and product-variety features.")

    df = df.assign(Revenue=df["Quantity"] * df["Price"])
    df = df[["Invoice", "StockCode", "Description", "Quantity", "Price", "Revenue",
             "InvoiceDate", "CustomerID", "Country"]].reset_index(drop=True)
    return df, log


def run() -> pd.DataFrame:
    """Load, clean, validate and save the transactions; write the cleaning log."""
    raw = load_raw()
    validate_raw(raw)
    df, log = clean(raw)
    validate_clean(df)
    CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    CLEANING_LOG_MD.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False)
    CLEANING_LOG_MD.write_text(log.to_markdown(len(raw), df), encoding="utf-8")
    logger.info("Saved %s and %s", CLEAN_CSV.name, CLEANING_LOG_MD.name)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    run()
