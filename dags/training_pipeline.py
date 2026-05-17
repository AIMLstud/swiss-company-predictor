"""Training pipeline DAG: feature matrix → XGBoost + quantile models → MLflow.

Runs weekly. Val/test boundaries are configurable via Airflow params so the
same DAG works for both scheduled runs and manual experiments.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="training_pipeline",
    schedule="@weekly",
    start_date=datetime(2026, 5, 1),
    catchup=False,
    max_active_runs=1,
    params={
        "val_start_year":  2025,
        "val_start_week":  1,
        "test_start_year": 2026,
        "test_start_week": 1,
        "experiment_name": "swiss_company_predictor",
    },
    tags=["training"],
)
def training_pipeline() -> None:

    @task()
    def check_data_availability() -> dict:
        """Fail early if raw.company_eintragsdatum has too few 'ok' rows."""
        from sqlalchemy import text

        from common.db import get_session

        with get_session() as session:
            row = session.execute(text("""
                SELECT COUNT(*) FROM raw.company_eintragsdatum
                WHERE scraping_status = 'ok'
            """)).fetchone()

        n = int(row[0]) if row else 0
        if n < 100:
            raise ValueError(
                f"Insufficient training data: {n} rows with scraping_status='ok' "
                "(need ≥ 100). Run feature_backfill first."
            )
        return {"n_ok": n}

    @task()
    def train_models(data_check: dict) -> dict:
        """Build feature matrix from DB, train p10/p50/p90 models, log to MLflow."""
        from airflow.operators.python import get_current_context

        from training.train import run_training

        params = get_current_context()["params"]

        run_id = run_training(
            val_start=(params["val_start_year"], params["val_start_week"]),
            test_start=(params["test_start_year"], params["test_start_week"]),
            experiment_name=params["experiment_name"],
        )
        return {"run_id": run_id, **data_check}

    train_models(check_data_availability())


training_pipeline()
