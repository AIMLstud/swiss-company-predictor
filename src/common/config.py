from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    app_db_url: str

    # ── Zefix REST API ────────────────────────────────────────────────────────
    zefix_username: str
    zefix_password: str
    zefix_base_url: str = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"

    # ── MLflow ────────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"

    # ── Pipeline knobs ────────────────────────────────────────────────────────
    zefix_canton: str = "LU"
    zefix_sleep_between: float = 0.1  # seconds between Zefix API calls
    hr_sleep_between: float = 0.2  # seconds between HR-Auszug calls
    hr_concurrency: int = 4  # parallel HR scraping workers
    hr_max_retries: int = 3  # retries on transient errors

    # ── Backfill seed CSV (optional) ──────────────────────────────────────────
    # If this file exists, the backfill DAG loads it directly instead of
    # running the full ~8h live scrape.
    seed_csv_path: Path = Path("tests/fixtures/260517_full_zefix_export_eintragsdatum.csv")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
