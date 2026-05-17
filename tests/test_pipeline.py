from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

from common.config import Settings
from scraper.hr_scraper import ViewStateMissingError
from scraper.pipeline import (
    stage1_full_sync,
    stage2_scrape_eintragsdatum,
    stage3_daily_sync,
)


def _cfg() -> Settings:
    return Settings(
        app_db_url="postgresql+psycopg://u:p@localhost/db",
        zefix_username="u",
        zefix_password="p",
        zefix_sleep_between=0.0,
        hr_sleep_between=0.0,
    )


def _session(rows: list | None = None) -> MagicMock:
    sess = MagicMock()
    if rows is not None:
        sess.execute.return_value.fetchall.return_value = rows
    return sess


_COMPANY: dict = {
    "uid": "CHE107251578",
    "name": "Test AG",
    "legalForm": {"id": 3, "shortName": "AG"},
    "status": "ACTIVE",
    "canton": "LU",
    "cantonalExcerptWeb": "https://lu.chregister.ch/cr-portal/auszug/auszug.xhtml?uid=CHE-107.251.578",
}

_URL = "https://lu.chregister.ch/cr-portal/auszug/auszug.xhtml?uid=CHE-107.251.578"


# ── stage1_full_sync ──────────────────────────────────────────────────────────

def test_stage1_calls_search_for_each_prefix() -> None:
    with patch("scraper.pipeline.search_by_name_prefix", return_value=[]) as mock_search:
        stage1_full_sync(_session(), settings=_cfg(), _sleep=lambda _: None)
    assert mock_search.call_count == 26


def test_stage1_returns_total_upserted() -> None:
    with patch("scraper.pipeline.search_by_name_prefix", return_value=[_COMPANY, _COMPANY]):
        total = stage1_full_sync(_session(), settings=_cfg(), _sleep=lambda _: None)
    assert total == 52  # 2 companies × 26 prefixes


def test_stage1_sleeps_after_each_prefix() -> None:
    sleep_calls: list[float] = []
    with patch("scraper.pipeline.search_by_name_prefix", return_value=[]):
        stage1_full_sync(_session(), settings=_cfg(), _sleep=sleep_calls.append)
    assert len(sleep_calls) == 26
    assert all(s == 0.0 for s in sleep_calls)


# ── stage2_scrape_eintragsdatum ────────────────────────────────────────────────

def test_stage2_records_ok() -> None:
    session = _session(rows=[("CHE107251578", _URL)])
    with patch("scraper.pipeline.scrape_with_retry", return_value=date(1998, 9, 7)):
        counts = stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    assert counts["ok"] == 1
    assert counts["no_date"] == 0


def test_stage2_records_no_date() -> None:
    session = _session(rows=[("CHE107251578", _URL)])
    with patch("scraper.pipeline.scrape_with_retry", return_value=None):
        counts = stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    assert counts["no_date"] == 1


def test_stage2_records_no_url() -> None:
    session = _session(rows=[("CHE107251578", None)])
    counts = stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    assert counts["no_url"] == 1


def test_stage2_records_viewstate_missing() -> None:
    session = _session(rows=[("CHE107251578", _URL)])
    with patch("scraper.pipeline.scrape_with_retry", side_effect=ViewStateMissingError("x")):
        counts = stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    assert counts["viewstate_missing"] == 1


def test_stage2_records_timeout() -> None:
    session = _session(rows=[("CHE107251578", _URL)])
    with patch("scraper.pipeline.scrape_with_retry", side_effect=requests.Timeout()):
        counts = stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    assert counts["timeout"] == 1


def test_stage2_records_http_error() -> None:
    session = _session(rows=[("CHE107251578", _URL)])
    with patch("scraper.pipeline.scrape_with_retry", side_effect=requests.HTTPError()):
        counts = stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    assert counts["http_error"] == 1


def test_stage2_upserts_eintragsdatum_row() -> None:
    session = _session(rows=[("CHE107251578", _URL)])
    with patch("scraper.pipeline.scrape_with_retry", return_value=date(1998, 9, 7)):
        stage2_scrape_eintragsdatum(session, settings=_cfg(), _sleep=lambda _: None)
    # 1 SELECT + 1 UPSERT
    assert session.execute.call_count == 2


# ── stage3_daily_sync ─────────────────────────────────────────────────────────

def test_stage3_upserts_new_companies() -> None:
    with (
        patch("scraper.pipeline.fetch_publications_by_date", return_value=[{}]),
        patch("scraper.pipeline.filter_new_entries_for_canton", return_value=["CHE107251578"]),
        patch("scraper.pipeline.fetch_detail", return_value=[_COMPANY]),
    ):
        count = stage3_daily_sync(
            _session(), date(2026, 5, 17), settings=_cfg(), _sleep=lambda _: None
        )
    assert count == 1


def test_stage3_fetches_for_correct_date() -> None:
    with (
        patch("scraper.pipeline.fetch_publications_by_date", return_value=[]) as mock_fetch,
        patch("scraper.pipeline.filter_new_entries_for_canton", return_value=[]),
    ):
        stage3_daily_sync(
            _session(), date(2026, 1, 7), settings=_cfg(), _sleep=lambda _: None
        )
    mock_fetch.assert_called_once_with(date(2026, 1, 7))


def test_stage3_returns_zero_when_no_new_companies() -> None:
    with (
        patch("scraper.pipeline.fetch_publications_by_date", return_value=[]),
        patch("scraper.pipeline.filter_new_entries_for_canton", return_value=[]),
    ):
        count = stage3_daily_sync(
            _session(), date(2026, 5, 17), settings=_cfg(), _sleep=lambda _: None
        )
    assert count == 0
