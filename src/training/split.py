"""Temporal train / val / test splitting for the weekly feature matrix."""

from datetime import date, timedelta
from typing import NamedTuple

import pandas as pd


def rolling_boundaries(
    reference: date,
    val_weeks: int = 52,
    test_weeks: int = 4,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return (val_start, test_start) as ISO (year, week) tuples relative to reference.

    test  = most recent test_weeks weeks ending at reference
    val   = val_weeks weeks immediately before test
    train = everything before val (grows automatically as new data arrives)
    """
    test_start_date = reference - timedelta(weeks=test_weeks)
    val_start_date  = test_start_date - timedelta(weeks=val_weeks)
    tc = test_start_date.isocalendar()
    vc = val_start_date.isocalendar()
    return (vc.year, vc.week), (tc.year, tc.week)


class Split(NamedTuple):
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


def temporal_split(
    df: pd.DataFrame,
    val_start: tuple[int, int],
    test_start: tuple[int, int],
) -> Split:
    """Split a weekly feature matrix into train / val / test by ISO year-week.

    The sort key is  iso_year * 100 + iso_week, so KW53 correctly falls
    between week 52 of the same year and week 1 of the next year.

    Args:
        df:         DataFrame with iso_year and iso_week columns.
        val_start:  (iso_year, iso_week) of the first validation row (inclusive).
        test_start: (iso_year, iso_week) of the first test row (inclusive).

    Raises:
        ValueError: if val_start > test_start.
    """
    if val_start > test_start:
        raise ValueError(f"val_start {val_start} must be ≤ test_start {test_start}")

    key = df["iso_year"].astype(int) * 100 + df["iso_week"].astype(int)
    val_key = val_start[0] * 100 + val_start[1]
    test_key = test_start[0] * 100 + test_start[1]

    return Split(
        train=df[key < val_key].reset_index(drop=True),
        val=df[(key >= val_key) & (key < test_key)].reset_index(drop=True),
        test=df[key >= test_key].reset_index(drop=True),
    )
