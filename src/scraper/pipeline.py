"""Stage 1 / 2 / 3 scraping pipeline functions.

Stage 1: full Zefix A–Z prefix-search backfill → raw.companies
Stage 2: HR-Auszug eintragsdatum scraping     → raw.company_eintragsdatum
Stage 3: daily SOGC publication sync           → raw.companies
"""

import json
import time
from collections.abc import Callable
from datetime import date
from typing import Any

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from common.config import Settings, get_settings
from scraper.hr_scraper import ViewStateMissingError, scrape_with_retry
from scraper.sogc_client import fetch_publications_by_date, filter_new_entries_for_canton
from scraper.zefix_client import fetch_detail, search_by_name_prefix

_PREFIXES: list[str] = [chr(c) for c in range(ord("A"), ord("Z") + 1)]

_UPSERT_COMPANY = text("""
    INSERT INTO raw.companies (
        uid, name, legalform_id, legalform_short, status, canton,
        cantonal_excerpt_web, raw_search, last_updated_at
    ) VALUES (
        :uid, :name, :legalform_id, :legalform_short, :status, :canton,
        :cantonal_excerpt_web, :raw_search::jsonb, now()
    )
    ON CONFLICT (uid) DO UPDATE SET
        name               = EXCLUDED.name,
        legalform_id       = EXCLUDED.legalform_id,
        legalform_short    = EXCLUDED.legalform_short,
        status             = EXCLUDED.status,
        canton             = EXCLUDED.canton,
        cantonal_excerpt_web = EXCLUDED.cantonal_excerpt_web,
        raw_search         = EXCLUDED.raw_search,
        last_updated_at    = now()
""")

_UPSERT_EINTRAGSDATUM = text("""
    INSERT INTO raw.company_eintragsdatum (uid, eintragsdatum, scraping_status, scraped_at)
    VALUES (:uid, :eintragsdatum, :scraping_status, now())
    ON CONFLICT (uid) DO UPDATE SET
        eintragsdatum   = EXCLUDED.eintragsdatum,
        scraping_status = EXCLUDED.scraping_status,
        scraped_at      = now()
""")

_SELECT_PENDING = text("""
    SELECT c.uid, c.cantonal_excerpt_web
    FROM raw.companies c
    LEFT JOIN raw.company_eintragsdatum e ON c.uid = e.uid
    WHERE e.uid IS NULL
       OR e.scraping_status NOT IN ('ok', 'no_date')
    ORDER BY c.uid
""")


def _row_from_zefix(company: dict[str, Any]) -> dict[str, Any]:
    lf = company.get("legalForm") or {}
    return {
        "uid": company.get("uid", ""),
        "name": company.get("name", ""),
        "legalform_id": lf.get("id"),
        "legalform_short": (lf.get("shortName") or {}).get("de") if isinstance(lf.get("shortName"), dict) else lf.get("shortName"),
        "status": company.get("status"),
        "canton": company.get("canton"),
        "cantonal_excerpt_web": company.get("cantonalExcerptWeb"),
        "raw_search": json.dumps(company),
    }


def stage1_full_sync(
    session: Session,
    canton: str = "LU",
    settings: Settings | None = None,
    _sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Search all A–Z prefixes for canton, upsert into raw.companies.

    Returns total number of rows upserted.
    """
    cfg = settings or get_settings()
    total = 0
    for prefix in _PREFIXES:
        results = search_by_name_prefix(prefix, canton=canton, active_only=False)
        for company in results:
            session.execute(_UPSERT_COMPANY, _row_from_zefix(company))
            total += 1
        _sleep(cfg.zefix_sleep_between)
    return total


def stage2_scrape_eintragsdatum(
    session: Session,
    settings: Settings | None = None,
    _sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Scrape eintragsdatum for all companies not yet successfully processed.

    Returns a counter dict keyed by scraping_status value.
    """
    cfg = settings or get_settings()
    rows = session.execute(_SELECT_PENDING).fetchall()

    counts: dict[str, int] = {
        "ok": 0, "no_date": 0, "no_url": 0,
        "viewstate_missing": 0, "http_error": 0, "timeout": 0, "error": 0,
    }

    for uid, url in rows:
        eintragsdatum: date | None = None

        if not url:
            status = "no_url"
        else:
            try:
                eintragsdatum = scrape_with_retry(url, max_retries=cfg.hr_max_retries)
                status = "ok" if eintragsdatum is not None else "no_date"
            except ViewStateMissingError:
                status = "viewstate_missing"
            except requests.Timeout:
                status = "timeout"
            except requests.HTTPError:
                status = "http_error"
            except Exception:
                status = "error"
            _sleep(cfg.hr_sleep_between)

        session.execute(_UPSERT_EINTRAGSDATUM, {
            "uid": uid,
            "eintragsdatum": eintragsdatum,
            "scraping_status": status,
        })
        counts[status] += 1

    return counts


def stage3_daily_sync(
    session: Session,
    d: date,
    canton: str = "LU",
    settings: Settings | None = None,
    _sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Fetch SOGC publications for date d, upsert newly registered companies.

    Returns count of rows upserted.
    """
    cfg = settings or get_settings()
    publications = fetch_publications_by_date(d)
    new_uids = filter_new_entries_for_canton(publications, canton)

    count = 0
    for uid in new_uids:
        details = fetch_detail(uid)
        for company in details:
            session.execute(_UPSERT_COMPANY, _row_from_zefix(company))
            count += 1
        _sleep(cfg.zefix_sleep_between)
    return count
