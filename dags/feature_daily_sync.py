"""Daily sync DAG: SOGC publications → new companies → eintragsdatum scraping.

Runs once per day. Uses the Airflow logical date (ds) as the SOGC publication
date, so re-running a past date re-processes that day's publications.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="feature_daily_sync",
    schedule="0 20 * * *",
    start_date=datetime(2026, 5, 1),
    catchup=False,
    max_active_runs=1,
    tags=["scraper", "features"],
)
def feature_daily_sync() -> None:

    @task()
    def sogc_sync() -> dict:
        """Fetch SOGC publications for the logical date, upsert new LU companies."""
        from datetime import date as _date

        from airflow.operators.python import get_current_context

        from common.config import get_settings
        from common.db import get_session
        from scraper.pipeline import stage3_daily_sync

        ds: str = get_current_context()["ds"]
        cfg = get_settings()

        with get_session() as session:
            n = stage3_daily_sync(session, _date.fromisoformat(ds), canton=cfg.zefix_canton)

        return {"date": ds, "new_companies": n}

    @task()
    def scrape_missing_eintragsdatum(upstream: dict) -> dict:
        """Scrape HR-Auszug eintragsdatum for companies that still lack it.

        Runs after sogc_sync so newly discovered companies are included.
        Also retries any previous failures with a retryable status.
        """
        from common.db import get_session
        from scraper.pipeline import stage2_scrape_eintragsdatum

        with get_session() as session:
            counts = stage2_scrape_eintragsdatum(session)

        return {**upstream, "scraping": counts}

    scrape_missing_eintragsdatum(sogc_sync())


feature_daily_sync()
