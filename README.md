# Swiss Company Predictor

Predicts the number of new company registrations per calendar week in Canton Lucerne (CH), with 80% prediction intervals (p10 / p50 / p90).

Data source: [Zefix REST API](https://www.zefix.admin.ch/ZefixPublicREST/) + Cantonal Commercial Register (HR-Auszug).

[![CI](https://github.com/AIMLstud/swiss-company-predictor/actions/workflows/ci.yml/badge.svg)](https://github.com/AIMLstud/swiss-company-predictor/actions/workflows/ci.yml)

---

## Architecture (FTI Pipeline)

```
Zefix REST API ──► feature_backfill (manual)
SOGC RSS feed  ──► feature_daily_sync (@daily)  ──► PostgreSQL (raw.*)
                                                         │
                                        training_pipeline (@weekly)
                                                 │
                                           MLflow tracking
                                                 │
                                       Streamlit dashboard ──► predictions
```

| Component           | Technology                              |
|---------------------|-----------------------------------------|
| Orchestration       | Apache Airflow 2.x (TaskFlow API)       |
| Feature store / DB  | PostgreSQL 18 (`raw` schema)            |
| Experiment tracking | MLflow (self-hosted)                    |
| Models              | XGBoost (p50) + GBM quantile (p10/p90) |
| UI                  | Streamlit + Plotly                      |

### Feature engineering

Weekly aggregates are built from raw `eintragsdatum` rows:

| Feature       | Description                                      |
|---------------|--------------------------------------------------|
| `iso_week`    | Calendar week (1–53)                             |
| `lag_1`       | Registrations in the previous week               |
| `lag_4`       | Registrations 4 weeks ago (monthly seasonality)  |
| `lag_52`      | Registrations 52 weeks ago (annual seasonality)  |
| `ag_share`    | Share of AGs in the preceding week               |
| `gmbh_share`  | Share of GmbHs in the preceding week             |

### Models

Three models are trained in each weekly run and stored in MLflow:

| Model     | Algorithm                          | Purpose              |
|-----------|------------------------------------|----------------------|
| `model_p50` | XGBoost                          | Point estimate       |
| `model_p10` | GradientBoostingRegressor α=0.10 | Lower bound (10th %)  |
| `model_p90` | GradientBoostingRegressor α=0.90 | Upper bound (90th %)  |

---

## Prerequisites

- Docker ≥ 24 and Docker Compose V2
- [uv](https://docs.astral.sh/uv/) ≥ 0.5

---

## Quick Start

```bash
cp .env.example .env
```

Open `.env` and fill in the three required values:
- `ZEFIX_USERNAME` / `ZEFIX_PASSWORD` — your Zefix API credentials
- `AIRFLOW__CORE__FERNET_KEY` — generate one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

```bash
docker compose up -d
```

| Service   | URL                    | Default login     |
|-----------|------------------------|-------------------|
| Airflow   | http://localhost:8080  | admin / admin     |
| MLflow    | http://localhost:5000  | —                 |
| pgAdmin   | http://localhost:5050  | admin@local.dev / admin |
| Streamlit | http://localhost:8501  | —                 |

### Seeding historical data (optional, recommended)

Running the live backfill scrapes ~35k companies from HR-Auszug and takes ~8h.
To skip this, place the seed CSV in `tests/fixtures/` before triggering the DAG:

```bash
cp /path/to/260517_full_zefix_export_eintragsdatum.csv tests/fixtures/
```

The `feature_backfill` DAG detects this file and loads it directly.

### First-time pipeline run

1. **Trigger `feature_backfill`** (manual, once) in the Airflow UI.
2. Wait for completion – Airflow will turn green.
3. `feature_daily_sync` runs automatically from that point on.
4. `training_pipeline` runs every Sunday midnight (@weekly); trigger it manually for the first model.
5. Open Streamlit at http://localhost:8501 to see predictions.

---

## Development

```bash
uv sync --all-extras          # install dev + all optional extras
uv run pytest -v              # run test suite
uv run ruff check src/        # lint
uv run mypy src/              # type-check
```

### Run training locally (without Docker)

```python
from training.train import run_training
run_training(
    val_start=(2024, 26),
    test_start=(2025, 1),
    tracking_uri="sqlite:///mlruns/mlflow.db",
)
```

### Run a prediction locally

```python
from inference.predict import predict_week
result = predict_week(2025, 20, tracking_uri="sqlite:///mlruns/mlflow.db")
print(result)  # {"p10": 12.3, "p50": 18.7, "p90": 24.1, "run_id": "..."}
```

---

## Repo Structure

```
src/
  common/        config, db helpers
  scraper/       zefix_client, sogc_client, hr_scraper, pipeline
  features/      aggregation, feature_builder
  training/      split, baseline, train
  inference/     predict
dags/
  feature_backfill.py       manual, seeds raw data
  feature_daily_sync.py     @daily, incremental sync
  training_pipeline.py      @weekly, trains + logs models
streamlit_app/
  app.py                    Streamlit UI
sql/init/                   PostgreSQL schema (raw.*)
docker/                     Dockerfiles per service
tests/                      unit + integration tests
  fixtures/                 weekly_sample.csv, seed CSV (optional)
```

---

## Environment Variables

| Variable                       | Required | Description                                |
|-------------------------------|----------|--------------------------------------------|
| `APP_DB_URL`                  | Yes      | SQLAlchemy URL for PostgreSQL              |
| `ZEFIX_USERNAME`              | Yes      | Zefix REST API credentials                 |
| `ZEFIX_PASSWORD`              | Yes      | Zefix REST API credentials                 |
| `MLFLOW_TRACKING_URI`         | No       | Defaults to `http://mlflow:5000`           |
| `SEED_CSV_PATH`               | No       | Path to seed CSV for instant backfill      |
| `AIRFLOW__CORE__FERNET_KEY`   | Yes      | Airflow encryption key                     |
