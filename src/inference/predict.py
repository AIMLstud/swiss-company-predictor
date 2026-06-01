"""Inference: load trained MLflow models and predict next-week registrations."""

from __future__ import annotations

import pandas as pd

from training.train import FEATURE_COLS


def _build_feature_row(
    weekly: pd.DataFrame,
    target_year: int,
    target_week: int,
) -> pd.DataFrame:
    """Return a single-row feature DataFrame for (target_year, target_week).

    Computes lags from the sorted weekly history.
    Raises ValueError when fewer than 52 preceding weeks are available.
    """
    target_key = target_year * 100 + target_week
    preceding = (
        weekly[weekly["iso_year"] * 100 + weekly["iso_week"] < target_key]
        .sort_values(["iso_year", "iso_week"])
        .reset_index(drop=True)
    )

    if len(preceding) < 52:
        raise ValueError(
            f"Need ≥52 weeks of history before ({target_year}, W{target_week:02d}), "
            f"have {len(preceding)}."
        )

    counts = preceding["n_registrations"]
    return pd.DataFrame(
        [
            {
                "iso_week": target_week,
                "lag_1": counts.iloc[-1],
                "lag_4": counts.iloc[-4],
                "lag_52": counts.iloc[-52],
                "ag_share": preceding["ag_share"].iloc[-1],
                "gmbh_share": preceding["gmbh_share"].iloc[-1],
            }
        ]
    )


def _get_latest_run_id(experiment_name: str, tracking_uri: str) -> str:
    """Return the run_id of the most recent FINISHED run in the experiment."""
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    runs = mlflow.search_runs(
        experiment_names=[experiment_name],
        filter_string="status = 'FINISHED'",
        order_by=["start_time DESC"],
        max_results=1,
    )
    assert isinstance(runs, pd.DataFrame)
    if runs.empty:
        raise ValueError(f"No finished MLflow runs found in experiment '{experiment_name}'.")
    return str(runs.iloc[0]["run_id"])


def predict_week(
    target_year: int,
    target_week: int,
    run_id: str | None = None,
    experiment_name: str = "swiss_company_predictor",
    tracking_uri: str | None = None,
    df: pd.DataFrame | None = None,
) -> dict[str, float | str]:
    """Predict registrations for ISO week (target_year, target_week).

    Returns:
        {"p10": float, "p50": float, "p90": float, "run_id": str}
    """
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost

    from common.config import get_settings
    from features.aggregation import aggregate_weekly
    from training.train import load_data

    cfg = get_settings()
    uri = tracking_uri or cfg.mlflow_tracking_uri
    mlflow.set_tracking_uri(uri)

    if run_id is None:
        run_id = _get_latest_run_id(experiment_name, uri)

    # Build feature vector (pass df to bypass DB in tests)
    if df is None:
        df = load_data()
    weekly = aggregate_weekly(df)
    X = _build_feature_row(weekly, target_year, target_week)[FEATURE_COLS].to_numpy()

    # Load models via URIs stored as run tags
    client = mlflow.MlflowClient()
    tags = client.get_run(run_id).data.tags

    p10 = mlflow.sklearn.load_model(tags["model_uri_p10"])
    p50 = mlflow.xgboost.load_model(tags["model_uri_p50"])
    p90 = mlflow.sklearn.load_model(tags["model_uri_p90"])

    return {
        "p10": max(0.0, float(p10.predict(X)[0])),
        "p50": max(0.0, float(p50.predict(X)[0])),
        "p90": max(0.0, float(p90.predict(X)[0])),
        "run_id": run_id,
    }
