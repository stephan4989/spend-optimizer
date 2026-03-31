"""
CSV validation for uploaded spend data.

Expected format:
    week,channel_a,channel_b,...,acquisitions
    2024-01-01,45000,32000,...,1240
    ...

Rules:
  - Required columns: 'week' and 'acquisitions'
  - All remaining columns are treated as media channels (1–10)
  - 'week' must be ISO 8601 dates (YYYY-MM-DD), weekly cadence
  - All spend and acquisitions values must be numeric and >= 0
  - Minimum 13 rows of data (one quarter)
  - File must be valid UTF-8 comma-delimited CSV
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd
from fastapi import HTTPException


REQUIRED_COLUMNS = {"week", "acquisitions"}
MAX_CHANNELS = 10
MIN_ROWS = 13


@dataclass
class ValidatedCSV:
    df: pd.DataFrame
    channels: list[str]
    rows: int
    week_start: str   # ISO date string
    week_end: str
    total_spend_per_channel: dict[str, float]


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

    # --- required columns ---
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        _fail(
            f"Missing required column(s): {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    # --- detect channels ---
    channels = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    if len(channels) == 0:
        _fail(
            "No media channel columns found. "
            "Add at least one spend column (any column that is not 'week' or 'acquisitions')."
        )
    if len(channels) > MAX_CHANNELS:
        _fail(
            f"Too many channels ({len(channels)}). "
            f"Maximum supported is {MAX_CHANNELS}. Found: {channels}"
        )

    # --- row count ---
    if len(df) < MIN_ROWS:
        _fail(
            f"Not enough data rows ({len(df)}). "
            f"Minimum required is {MIN_ROWS} weeks."
        )

    # --- week column: parseable dates ---
    try:
        weeks = pd.to_datetime(df["week"], format="%Y-%m-%d")
    except Exception:
        _fail(
            "Column 'week' contains values that cannot be parsed as dates. "
            "Expected format: YYYY-MM-DD (e.g. 2024-01-08)."
        )

    # --- no missing values in numeric columns ---
    numeric_cols = channels + ["acquisitions"]
    missing_values = df[numeric_cols].isnull().any()
    cols_with_nulls = missing_values[missing_values].index.tolist()
    if cols_with_nulls:
        _fail(f"Missing values found in column(s): {cols_with_nulls}")

    # --- numeric types ---
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            _fail(
                f"Column '{col}' must contain numeric values only. "
                f"Found non-numeric entries."
            )

    # --- no negative values ---
    for col in numeric_cols:
        if (df[col] < 0).any():
            _fail(f"Column '{col}' contains negative values. All spend and acquisitions must be >= 0.")

    # --- assemble result ---
    week_start = weeks.min().strftime("%Y-%m-%d")
    week_end = weeks.max().strftime("%Y-%m-%d")
    total_spend = {ch: float(df[ch].sum()) for ch in channels}

    return ValidatedCSV(
        df=df,
        channels=channels,
        rows=len(df),
        week_start=week_start,
        week_end=week_end,
        total_spend_per_channel=total_spend,
    )


def _fail(message: str) -> None:
    raise HTTPException(
        status_code=422,
        detail=message,
    )
