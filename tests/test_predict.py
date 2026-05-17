from datetime import date, timedelta

import pandas as pd
import pytest

from inference.predict import _build_feature_row, _get_latest_run_id, predict_week


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "u")
    monkeypatch.setenv("ZEFIX_PASSWORD", "p")


def _weekly(n: int) -> pd.DataFrame:
    """n rows of weekly aggregate data starting at ISO 2020-W01."""
    start = date(2019, 12, 30)  # 2020-W01 Monday
    rows = []
    for i in range(n):
        d = start + timedelta(weeks=i)
        iso = d.isocalendar()
        rows.append({
            "iso_year":       iso.year,
            "iso_week":       iso.week,
            "n_registrations": 5 + i % 8,
            "ag_share":       0.6,
            "gmbh_share":     0.4,
        })
    return pd.DataFrame(rows)


def _synthetic_raw(n: int = 120) -> pd.DataFrame:
    """Raw company rows – one AG + one GmbH per week for n weeks."""
    start = date(2019, 12, 30)
    rows = []
    for i in range(n):
        d = start + timedelta(weeks=i)
        rows.append({"eintragsdatum": d.isoformat(), "legalform_short": "AG"})
        rows.append({"eintragsdatum": d.isoformat(), "legalform_short": "GmbH"})
    return pd.DataFrame(rows)


# ── _build_feature_row ────────────────────────────────────────────────────────

def test_build_feature_row_lag_values() -> None:
    weekly = _weekly(60)
    # target = week after the last row; preceding = all 60 rows
    last = weekly.iloc[-1]
    target_year = int(last["iso_year"])
    target_week = int(last["iso_week"]) + 1
    if target_week > 52:
        target_week = 1
        target_year += 1

    row = _build_feature_row(weekly, target_year, target_week)
    assert row.iloc[0]["lag_1"]  == weekly["n_registrations"].iloc[-1]
    assert row.iloc[0]["lag_4"]  == weekly["n_registrations"].iloc[-4]
    assert row.iloc[0]["lag_52"] == weekly["n_registrations"].iloc[-52]


def test_build_feature_row_correct_iso_week() -> None:
    weekly = _weekly(60)
    row = _build_feature_row(weekly, 2021, 15)
    assert row.iloc[0]["iso_week"] == 15


def test_build_feature_row_raises_insufficient_history() -> None:
    weekly = _weekly(30)  # only 30 rows
    with pytest.raises(ValueError, match="52"):
        _build_feature_row(weekly, 2020, 53)


def test_build_feature_row_uses_latest_legalform_shares() -> None:
    weekly = _weekly(60)
    weekly.loc[weekly.index[-1], "ag_share"] = 0.75
    last = weekly.iloc[-1]
    target_year, target_week = int(last["iso_year"]), int(last["iso_week"]) + 1
    if target_week > 52:
        target_week, target_year = 1, target_year + 1
    row = _build_feature_row(weekly, target_year, target_week)
    assert row.iloc[0]["ag_share"] == pytest.approx(0.75)


# ── integration: predict_week ─────────────────────────────────────────────────

@pytest.fixture()
def trained_run(tmp_path) -> tuple[str, str]:
    """Train models with a local MLflow store; return (run_id, tracking_uri)."""
    from training.train import run_training

    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    run_id = run_training(
        df=_synthetic_raw(),
        val_start=(2021, 26),
        test_start=(2021, 40),
        tracking_uri=tracking_uri,
    )
    return run_id, tracking_uri


def test_predict_week_returns_expected_keys(trained_run) -> None:
    run_id, tracking_uri = trained_run
    result = predict_week(
        2021, 45, run_id=run_id, tracking_uri=tracking_uri,
        df=_synthetic_raw(),
    )
    assert set(result.keys()) == {"p10", "p50", "p90", "run_id"}
    assert result["run_id"] == run_id


def test_predict_week_quantile_ordering(trained_run) -> None:
    run_id, tracking_uri = trained_run
    result = predict_week(2021, 45, run_id=run_id, tracking_uri=tracking_uri,
                          df=_synthetic_raw())
    assert result["p10"] <= result["p50"] <= result["p90"]


def test_predict_week_non_negative(trained_run) -> None:
    run_id, tracking_uri = trained_run
    result = predict_week(2021, 45, run_id=run_id, tracking_uri=tracking_uri,
                          df=_synthetic_raw())
    assert result["p10"] >= 0.0
    assert result["p50"] >= 0.0
    assert result["p90"] >= 0.0


def test_get_latest_run_id(trained_run) -> None:
    _, tracking_uri = trained_run
    run_id = _get_latest_run_id("swiss_company_predictor", tracking_uri)
    assert isinstance(run_id, str) and len(run_id) == 32
