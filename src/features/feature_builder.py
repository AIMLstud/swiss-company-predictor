"""Lag-feature construction for the weekly registration time series."""

import pandas as pd

from features.aggregation import aggregate_weekly

_DEFAULT_LAGS: tuple[int, ...] = (1, 4, 52)


def add_lag_features(
    weekly: pd.DataFrame,
    lags: tuple[int, ...] = _DEFAULT_LAGS,
) -> pd.DataFrame:
    """Add lag_N columns for n_registrations to a sorted weekly DataFrame.

    Assumes the series has no missing weeks; uses row-based shifting.
    """
    result = weekly.sort_values(["iso_year", "iso_week"]).copy().reset_index(drop=True)
    for n in lags:
        result[f"lag_{n}"] = result["n_registrations"].shift(n)
    return result


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Raw company DataFrame → feature matrix ready for ML.

    Pipeline: aggregate_weekly → add_lag_features → drop rows with NaN lags.
    """
    weekly = aggregate_weekly(df)
    with_lags = add_lag_features(weekly)
    lag_cols = [c for c in with_lags.columns if c.startswith("lag_")]
    return with_lags.dropna(subset=lag_cols).reset_index(drop=True)
