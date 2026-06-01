from datetime import date, timedelta

import pandas as pd
import pytest

from training.baseline import lag1_baseline, lag52_baseline
from training.train import run_training


@pytest.fixture(autouse=True)
def _training_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "u")
    monkeypatch.setenv("ZEFIX_PASSWORD", "p")


# ── helpers ───────────────────────────────────────────────────────────────────


def _baseline_df() -> pd.DataFrame:
    """Small weekly DataFrame with known lag values for baseline assertions."""
    return pd.DataFrame(
        {
            "n_registrations": [10, 12, 15, 8],
            "lag_1": [8, 10, 12, 15],
            "lag_52": [9, 11, 14, 7],
        }
    )


def _synthetic_raw(n: int = 120) -> pd.DataFrame:
    """n weekly rows starting at ISO 2020-W01. One AG and one GmbH per week."""
    start = date(2019, 12, 30)  # Monday of 2020-W01
    rows = []
    for i in range(n):
        d = start + timedelta(weeks=i)
        rows.append({"eintragsdatum": d.isoformat(), "legalform_short": "AG"})
        rows.append({"eintragsdatum": d.isoformat(), "legalform_short": "GmbH"})
    return pd.DataFrame(rows)


# ── baseline metrics ──────────────────────────────────────────────────────────


def test_lag1_mae_correct() -> None:
    df = _baseline_df()
    # errors: |10-8|=2, |12-10|=2, |15-12|=3, |8-15|=7  → mean = 3.5
    result = lag1_baseline(df)
    assert pytest.approx(result.mae, rel=1e-6) == 3.5


def test_lag52_mae_correct() -> None:
    df = _baseline_df()
    # errors all 1 → MAE = 1.0
    result = lag52_baseline(df)
    assert pytest.approx(result.mae, rel=1e-6) == 1.0


def test_metrics_zero_error() -> None:
    df = pd.DataFrame({"n_registrations": [5, 10], "lag_1": [5, 10], "lag_52": [5, 10]})
    assert lag1_baseline(df).mae == 0.0
    assert lag1_baseline(df).rmse == 0.0


def test_rmse_gte_mae() -> None:
    result = lag1_baseline(_baseline_df())
    assert result.rmse >= result.mae


# ── run_training integration ──────────────────────────────────────────────────


def test_run_training_returns_run_id(tmp_path) -> None:
    run_id = run_training(
        df=_synthetic_raw(),
        val_start=(2021, 26),
        test_start=(2021, 40),
        tracking_uri=str(tmp_path / "mlruns"),
    )
    assert isinstance(run_id, str) and len(run_id) == 32


def test_run_training_logs_p50_metric(tmp_path) -> None:
    import mlflow

    tracking_uri = str(tmp_path / "mlruns")
    run_id = run_training(
        df=_synthetic_raw(),
        val_start=(2021, 26),
        test_start=(2021, 40),
        tracking_uri=tracking_uri,
    )

    mlflow.set_tracking_uri(tracking_uri)
    run = mlflow.get_run(run_id)
    assert "p50_mae_val" in run.data.metrics
    assert "baseline_lag1_mae" in run.data.metrics


def test_run_training_logs_three_models(tmp_path) -> None:
    import mlflow

    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    run_id = run_training(
        df=_synthetic_raw(),
        val_start=(2021, 26),
        test_start=(2021, 40),
        tracking_uri=tracking_uri,
    )

    client = mlflow.MlflowClient(tracking_uri=tracking_uri)
    tags = client.get_run(run_id).data.tags
    assert {"model_uri_p50", "model_uri_p10", "model_uri_p90"} <= tags.keys()
