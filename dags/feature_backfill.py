"""Backfill DAG: populate raw.companies + raw.company_eintragsdatum.

Fast path  – seed CSV present  → loads pre-scraped data directly (seconds).
Slow path  – no seed CSV        → Stage 1 A–Z search + Stage 2 HR-Auszug scrape (~8 h).
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="feature_backfill",
    schedule=None,          # one-shot: trigger manually
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["scraper", "features"],
)
def feature_backfill() -> None:

    @task()
    def stage1_or_seed() -> dict:
        """Upsert companies from seed CSV, or run Stage 1 Zefix A–Z search."""
        from pathlib import Path

        import pandas as pd
        from sqlalchemy import text

        from common.config import get_settings
        from common.db import get_session
        from scraper.pipeline import stage1_full_sync

        cfg = get_settings()
        seed = Path(cfg.seed_csv_path)

        if seed.exists():
            df = (
                pd.read_csv(seed, low_memory=False)
                .rename(columns={
                    "name_detail": "name",
                    "legalForm.id_detail": "legalform_id",
                    "legalForm.shortName.de_detail": "legalform_short",
                    "status_detail": "status",
                })
            )
            df = df[df["canton"] == cfg.zefix_canton].copy()

            def _v(row: pd.Series, col: str):
                val = row.get(col)
                return None if pd.isna(val) else val

            records = [
                {
                    "uid": row["uid"],
                    "name": _v(row, "name") or "",
                    "legalform_id": int(row["legalform_id"]) if pd.notna(row.get("legalform_id")) else None,
                    "legalform_short": _v(row, "legalform_short"),
                    "status": _v(row, "status"),
                    "canton": _v(row, "canton"),
                    "cantonal_excerpt_web": _v(row, "cantonalExcerptWeb"),
                }
                for _, row in df.iterrows()
            ]

            upsert_sql = text("""
                INSERT INTO raw.companies (
                    uid, name, legalform_id, legalform_short, status, canton,
                    cantonal_excerpt_web, last_updated_at
                ) VALUES (
                    :uid, :name, :legalform_id, :legalform_short, :status, :canton,
                    :cantonal_excerpt_web, now()
                )
                ON CONFLICT (uid) DO UPDATE SET
                    name                 = EXCLUDED.name,
                    legalform_id         = EXCLUDED.legalform_id,
                    legalform_short      = EXCLUDED.legalform_short,
                    status               = EXCLUDED.status,
                    canton               = EXCLUDED.canton,
                    cantonal_excerpt_web = EXCLUDED.cantonal_excerpt_web,
                    last_updated_at      = now()
            """)

            with get_session() as session:
                session.execute(upsert_sql, records)

            return {"used_seed": True, "n_companies": len(records)}

        with get_session() as session:
            n = stage1_full_sync(session, canton=cfg.zefix_canton)
        return {"used_seed": False, "n_companies": n}

    @task()
    def stage2_eintragsdatum(upstream: dict) -> dict:
        """Load eintragsdatum from seed CSV, or run Stage 2 HR-Auszug scraping."""
        from pathlib import Path

        import pandas as pd
        from sqlalchemy import text

        from common.config import get_settings
        from common.db import get_session
        from scraper.pipeline import stage2_scrape_eintragsdatum

        cfg = get_settings()

        if upstream.get("used_seed"):
            seed = Path(cfg.seed_csv_path)
            df = pd.read_csv(seed, low_memory=False)
            df = df[df["canton"] == cfg.zefix_canton].dropna(subset=["eintragsdatum"]).copy()

            records = [
                {"uid": row["uid"], "eintragsdatum": row["eintragsdatum"]}
                for _, row in df.iterrows()
            ]

            upsert_sql = text("""
                INSERT INTO raw.company_eintragsdatum (uid, eintragsdatum, scraping_status)
                VALUES (:uid, :eintragsdatum, 'ok')
                ON CONFLICT (uid) DO NOTHING
            """)

            with get_session() as session:
                session.execute(upsert_sql, records)

            return {"source": "csv", "rows": len(records)}

        with get_session() as session:
            counts = stage2_scrape_eintragsdatum(session)
        return {"source": "live", **counts}

    stage2_eintragsdatum(stage1_or_seed())


feature_backfill()
