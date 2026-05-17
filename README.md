# Swiss Company Predictor

Predicts the number of new company registrations per calendar week in Canton Lucerne (CH).

Data source: [Zefix REST API](https://www.zefix.admin.ch/ZefixPublicREST/) + Cantonal Commercial Register (HR).

## Architecture

FTI-Pipeline (Feature / Training / Inference):

| Component | Technology |
|---|---|
| Orchestration | Apache Airflow 2.x |
| Feature Store / DB | PostgreSQL 18 (`raw`, `features`, `predictions` schemas) |
| Experiment Tracking | MLflow (self-hosted) |
| UI | Streamlit |
| Model | XGBoost + quantile regression (90% CI) |

## Prerequisites

- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) ≥ 0.5

## Quick Start

```bash
cp .env.example .env
# Edit .env: fill in ZEFIX_USERNAME, ZEFIX_PASSWORD, AIRFLOW__CORE__FERNET_KEY

# Optional: place seed CSV to skip the ~8h live backfill
# cp /path/to/260517_full_zefix_export_eintragsdatum.csv tests/fixtures/

docker compose up -d
```

| Service | URL |
|---|---|
| Airflow | http://localhost:8080 |
| MLflow | http://localhost:5001 |
| pgAdmin | http://localhost:5050 |
| Streamlit | http://localhost:8501 |

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check src/
uv run mypy src/
```

## Pipeline Overview

1. **Backfill** (`feature_backfill` DAG, manual trigger): seeds `raw.companies` from all ~35k active LU firms via Zefix prefix search + HR scraping. Detects `tests/fixtures/260517_full_zefix_export_eintragsdatum.csv` for instant seeding.
2. **Daily Sync** (`feature_daily_sync` DAG, `@daily`): ingests new registrations from SOGC publications.
3. **Training** (`training_pipeline` DAG, `@weekly`): trains XGBoost model, registers best version in MLflow.
4. **Inference**: on-demand from Streamlit; loads Production model from MLflow Registry.

## Repo Structure

```
src/
  common/       config, db, logging
  scraper/      zefix_client, sogc_client, hr_scraper, pipeline
  features/     aggregation, feature_builder
  training/     split, baseline, train
  inference/    predict
dags/           Airflow DAG definitions
streamlit_app/  UI
sql/init/       PostgreSQL init scripts
docker/         Dockerfiles per service
tests/          unit tests + fixtures
```
