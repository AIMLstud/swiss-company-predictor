"""XGBoost training pipeline with MLflow tracking and quantile prediction intervals."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLS: list[str] = [
    "iso_week", "lag_1", "lag_4", "lag_52", "ag_share", "gmbh_share",
]
TARGET_COL = "n_registrations"

_XGB_PARAMS: dict = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}

_GBM_PARAMS: dict = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "random_state": 42,
}


def load_data() -> pd.DataFrame:
    """Load company + eintragsdatum from raw schema (requires live DB)."""
    from sqlalchemy import text

    from common.db import get_engine

    with get_engine().connect() as conn:
        return pd.read_sql(
            text("""
                SELECT c.uid, e.eintragsdatum, c.legalform_short
                FROM raw.companies c
                JOIN raw.company_eintragsdatum e ON c.uid = e.uid
                WHERE e.scraping_status = 'ok'
            """),
            conn,
        )


def run_training(
    df: pd.DataFrame | None = None,
    val_start: tuple[int, int] = (2025, 1),
    test_start: tuple[int, int] = (2026, 1),
    experiment_name: str = "swiss_company_predictor",
    tracking_uri: str | None = None,
) -> str:
    """Build features, split, train three quantile models, log to MLflow.

    Args:
        df:            Raw company DataFrame (uid, eintragsdatum, legalform_short).
                       If None, loads from DB via load_data().
        val_start:     (iso_year, iso_week) of first validation row.
        test_start:    (iso_year, iso_week) of first test row.
        experiment_name: MLflow experiment name.
        tracking_uri:  Override for MLflow tracking URI (useful in tests).

    Returns:
        MLflow run_id string.
    """
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost
    import xgboost as xgb
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error

    from common.config import get_settings
    from features.feature_builder import build_feature_matrix
    from training.baseline import lag1_baseline, lag52_baseline
    from training.split import temporal_split

    cfg = get_settings()
    mlflow.set_tracking_uri(tracking_uri or cfg.mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    if df is None:
        df = load_data()

    features = build_feature_matrix(df)
    split = temporal_split(features, val_start=val_start, test_start=test_start)

    X_train = split.train[FEATURE_COLS].to_numpy()
    y_train = split.train[TARGET_COL].to_numpy()
    X_val   = split.val[FEATURE_COLS].to_numpy()
    y_val   = split.val[TARGET_COL].to_numpy()

    with mlflow.start_run() as run:
        mlflow.log_params({
            "val_start":  str(val_start),
            "test_start": str(test_start),
            "n_train":    len(split.train),
            "n_val":      len(split.val),
            "n_test":     len(split.test),
            "features":   ",".join(FEATURE_COLS),
            **{f"xgb_{k}": v for k, v in _XGB_PARAMS.items()},
        })

        if len(split.val) > 0:
            for label, result in [
                ("lag1",  lag1_baseline(split.val)),
                ("lag52", lag52_baseline(split.val)),
            ]:
                mlflow.log_metrics({
                    f"baseline_{label}_mae":  result.mae,
                    f"baseline_{label}_rmse": result.rmse,
                })

        # ── p50: XGBoost point estimate ───────────────────────────────────
        p50 = xgb.XGBRegressor(**_XGB_PARAMS)
        p50.fit(X_train, y_train)
        if len(X_val) > 0:
            mlflow.log_metric("p50_mae_val", mean_absolute_error(y_val, p50.predict(X_val)))
        model_uris: dict[str, str] = {
            "model_uri_p50": mlflow.xgboost.log_model(p50, name="model_p50").model_uri,
        }

        # ── p10 / p90: GBM quantile prediction intervals ──────────────────
        for quantile, alpha in [(10, 0.1), (90, 0.9)]:
            q_model = GradientBoostingRegressor(loss="quantile", alpha=alpha, **_GBM_PARAMS)
            q_model.fit(X_train, y_train)
            if len(X_val) > 0:
                mlflow.log_metric(
                    f"p{quantile}_mae_val",
                    mean_absolute_error(y_val, q_model.predict(X_val)),
                )
            model_uris[f"model_uri_p{quantile}"] = mlflow.sklearn.log_model(
                q_model, name=f"model_p{quantile}"
            ).model_uri

        # store model URIs as tags so predict.py can load them by run_id
        mlflow.set_tags(model_uris)

    return run.info.run_id
