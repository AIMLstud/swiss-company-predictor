from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from features.aggregation import aggregate_weekly
from features.feature_builder import add_lag_features, build_feature_matrix

FIXTURES = Path(__file__).parent / "fixtures"


def _csv() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "weekly_sample.csv")


def _weekly_rows(n: int, n_per_week: int = 1) -> pd.DataFrame:
    """Generate n consecutive weekly rows starting at ISO 2020-W01."""
    start = date(2019, 12, 30)  # Monday of 2020-W01
    rows = []
    for i in range(n):
        d = start + timedelta(weeks=i)
        for _ in range(n_per_week):
            rows.append({"eintragsdatum": d.isoformat(), "legalform_short": "AG"})
    return pd.DataFrame(rows)


# ── aggregate_weekly ──────────────────────────────────────────────────────────


def test_aggregate_row_count() -> None:
    result = aggregate_weekly(_csv())
    # fixture has 4 distinct ISO weeks
    assert len(result) == 4


def test_aggregate_n_registrations() -> None:
    result = aggregate_weekly(_csv())
    # 2024-W02 has 3 registrations; sort puts it second (after 2020-W53)
    assert result.loc[result["iso_week"] == 2, "n_registrations"].iloc[0] == 3


def test_aggregate_ag_share() -> None:
    result = aggregate_weekly(_csv())
    row = result[(result["iso_year"] == 2024) & (result["iso_week"] == 2)].iloc[0]
    assert pytest.approx(row["ag_share"], rel=1e-3) == 2 / 3


def test_aggregate_gmbh_share() -> None:
    result = aggregate_weekly(_csv())
    row = result[(result["iso_year"] == 2024) & (result["iso_week"] == 2)].iloc[0]
    assert pytest.approx(row["gmbh_share"], rel=1e-3) == 1 / 3


def test_aggregate_sorted_ascending() -> None:
    result = aggregate_weekly(_csv())
    keys = list(zip(result["iso_year"], result["iso_week"], strict=True))
    assert keys == sorted(keys)


def test_aggregate_kw53() -> None:
    # 2020-12-28 (Monday) is ISO week 2020-W53
    df = pd.DataFrame({"eintragsdatum": ["2020-12-28"], "legalform_short": ["AG"]})
    result = aggregate_weekly(df)
    assert result.iloc[0]["iso_year"] == 2020
    assert result.iloc[0]["iso_week"] == 53


def test_aggregate_null_legalform_counted_but_not_ag_gmbh() -> None:
    df = pd.DataFrame(
        {
            "eintragsdatum": ["2024-01-08", "2024-01-08"],
            "legalform_short": ["AG", None],
        }
    )
    result = aggregate_weekly(df)
    assert result.iloc[0]["n_registrations"] == 2
    assert pytest.approx(result.iloc[0]["ag_share"]) == 0.5
    assert pytest.approx(result.iloc[0]["gmbh_share"]) == 0.0


# ── add_lag_features ──────────────────────────────────────────────────────────


def test_add_lag_values() -> None:
    weekly = aggregate_weekly(_weekly_rows(5, n_per_week=3))
    result = add_lag_features(weekly, lags=(1,))
    # row 0 → lag_1 NaN; row 1 → lag_1 == n_registrations[0]
    assert pd.isna(result.loc[0, "lag_1"])
    assert result.loc[1, "lag_1"] == result.loc[0, "n_registrations"]


def test_add_lag_first_rows_nan() -> None:
    weekly = aggregate_weekly(_weekly_rows(10))
    result = add_lag_features(weekly, lags=(4,))
    assert result["lag_4"].isna().sum() == 4
    assert pd.notna(result.loc[4, "lag_4"])


# ── build_feature_matrix ──────────────────────────────────────────────────────


def test_build_feature_matrix_drops_insufficient_history() -> None:
    # 4 weeks is not enough to compute lag_52
    result = build_feature_matrix(_csv())
    assert len(result) == 0


def test_build_feature_matrix_shape_with_full_history() -> None:
    # 60 consecutive weeks → 60 - 52 = 8 rows after dropna(lag_52)
    result = build_feature_matrix(_weekly_rows(60))
    assert len(result) == 8
    assert {"lag_1", "lag_4", "lag_52", "ag_share", "gmbh_share"}.issubset(result.columns)


def test_build_feature_matrix_no_nan() -> None:
    result = build_feature_matrix(_weekly_rows(60))
    assert not result.isnull().any().any()
