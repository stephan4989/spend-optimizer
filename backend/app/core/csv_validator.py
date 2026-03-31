"""
CSV validation for uploaded spend data.

Expected format:
    date,channel_a,channel_b,...,acquisitions
    2024-01-01,45000,32000,...,1240
    ...

The date column can be named 'date', 'week', or 'month'.
Granularity (daily / weekly / monthly) is auto-detected from the median
gap between consecutive dates.

Rules:
  - Required columns: a date column ('date', 'week', or 'month') and 'acquisitions'
  - All remaining columns are treated as media channels (1–10)
  - Date column must be ISO 8601 dates (YYYY-MM-DD)
  - All spend and acquisitions values must be numeric and >= 0
  - Minimum rows: 13 (weekly), 60 (daily), 6 (monthly)
  - File must be valid UTF-8 comma-delimited CSV
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd
from fastapi import HTTPException

DATE_COLUMN_ALIASES = {"date", "week", "month"}
REQUIRED_FIXED = {"acquisitions"}
MAX_CHANNELS = 10

# Minimum rows per granularity
MIN_ROWS: dict[str, int] = {
    "daily":   60,
    "weekly":  13,
    "monthly":  6,
}


@dataclass
class ValidatedCSV:
    df: pd.DataFrame
    channels: list[str]
    rows: int
    date_start: str        # ISO date string
    date_end: str
    granularity: str       # 'daily' | 'weekly' | 'monthly'
    date_col: str          # actual column name used ('date', 'week', or 'month')
    total_spend_per_channel: dict[str, float]


def _detect_granularity(dates: pd.Series) -> str:
    """Infer daily / weekly / monthly from the median gap between dates."""
    sorted_dates = dates.sort_values()
    gaps = sorted_dates.diff().dropna().dt.days
    if gaps.empty:
        return "weekly"
    median_gap = gaps.median()
    if median_gap <= 2:
        return "daily"
    elif median_gap <= 10:
        return "weekly"
    else:
        return "monthly"


def validate_csv(raw_bytes: bytes, filename: str = "") -> ValidatedCSV:
    """
    Parse and validate raw CSV bytes.

    Returns a ValidatedCSV on success.
    Raises HTTPException(422) with a descriptive message on any validation failure.
    """
    # --- parse ---
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:
        _fail(f"Could not parse '{filename}' as CSV: {exc}")

    # --- find date column ---
    date_col = None
    for alias in DATE_COLUMN_ALIASES:
        if alias in df.columns:
            date_col = alias
            break
    if date_col is None:
        _fail(
            "Missing date column. Expected a column named 'date', 'week', or 'month'. "
            f"Found columns: {list(df.columns)}"
        )

    # --- required fixed columns ---
    if "acquisitions" not in df.columns:
        _fail(
            f"Missing required column 'acquisitions'. "
            f"Found columns: {list(df.columns)}"
        )

    # --- detect channels ---
    reserved = DATE_COLUMN_ALIASES | {"acquisitions"}
    channels = [c for c in df.columns if c not in reserved]
    if len(channels) == 0:
        _fail(
            "No media channel columns found. "
            "Add at least one spend column (any column that is not the date or 'acquisitions')."
        )
    if len(channels) > MAX_CHANNELS:
        _fail(
            f"Too many channels ({len(channels)}). "
            f"Maximum supported is {MAX_CHANNELS}. Found: {channels}"
        )

    # --- date column: parseable ---
    try:
        dates = pd.to_datetime(df[date_col], format="%Y-%m-%d")
    except Exception:
        _fail(
            f"Column '{date_col}' contains values that cannot be parsed as dates. "
            "Expected format: YYYY-MM-DD (e.g. 2024-01-08)."
        )

    # --- detect granularity ---
    granularity = _detect_granularity(dates)

    # --- row count ---
    min_rows = MIN_ROWS[granularity]
    if len(df) < min_rows:
        _fail(
            f"Not enough data rows ({len(df)}) for {granularity} data. "
            f"Minimum required is {min_rows} rows."
        )

    # --- no missing values in numeric columns ---
    numeric_cols = channels + ["acquisitions"]
    cols_with_nulls = df[numeric_cols].isnull().any()
    nulls = cols_with_nulls[cols_with_nulls].index.tolist()
    if nulls:
        _fail(f"Missing values found in column(s): {nulls}")

    # --- numeric types ---
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            _fail(
                f"Column '{col}' must contain numeric values only. "
                "Found non-numeric entries."
            )

    # --- no negative values ---
    for col in numeric_cols:
        if (df[col] < 0).any():
            _fail(f"Column '{col}' contains negative values. All spend and acquisitions must be >= 0.")

    # Normalise date column name to 'date' internally for the model
    if date_col != "date":
        df = df.rename(columns={date_col: "date"})

    date_start = dates.min().strftime("%Y-%m-%d")
    date_end   = dates.max().strftime("%Y-%m-%d")
    total_spend = {ch: float(df[ch].sum()) for ch in channels}

    return ValidatedCSV(
        df=df,
        channels=channels,
        rows=len(df),
        date_start=date_start,
        date_end=date_end,
        granularity=granularity,
        date_col=date_col,
        total_spend_per_channel=total_spend,
    )


def _fail(message: str) -> None:
    raise HTTPException(status_code=422, detail=message)
