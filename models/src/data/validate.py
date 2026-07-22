"""Validation utilities for OHLCV data."""

from __future__ import annotations

import pandas as pd


class ValidationReport:
    """Report generated after validating OHLCV data."""

    def __init__(self, duplicates_removed: int) -> None:
        self.duplicates_removed = duplicates_removed


def validate_ohlcv(
    df: pd.DataFrame,
    min_valid_candle_ratio: float = 0.5,
) -> tuple[pd.DataFrame, ValidationReport]:
    """Validate and clean OHLCV data."""
    initial_len = len(df)

    # Remove duplicates
    cleaned_df = df.drop_duplicates().reset_index(drop=True)

    duplicates_removed = initial_len - len(cleaned_df)
    report = ValidationReport(duplicates_removed=duplicates_removed)

    return cleaned_df, report
