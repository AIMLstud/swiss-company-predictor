import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import requests
import responses as rsps_lib

from scraper.sogc_client import fetch_publications_by_date, filter_new_entries_for_canton

FIXTURES = Path(__file__).parent / "fixtures"
SOGC_BASE = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/sogc/bydate"


def load(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def zefix_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "testuser")
    monkeypatch.setenv("ZEFIX_PASSWORD", "testpass")
    monkeypatch.setenv("ZEFIX_BASE_URL", "https://www.zefix.admin.ch/ZefixPublicREST/api/v1")


# ── fetch_publications_by_date ────────────────────────────────────────────────

def test_fetch_returns_list() -> None:
    fixture = load("sogc_bydate_response.json")
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{SOGC_BASE}/2026-05-15", json=fixture)
        result = fetch_publications_by_date(date(2026, 5, 15))
    assert len(result) == 4


def test_fetch_uses_iso_date_in_url() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{SOGC_BASE}/2026-01-07", json=[])
        fetch_publications_by_date(date(2026, 1, 7))
        assert rsps.calls[0].request.url.endswith("2026-01-07")


def test_fetch_handles_wrapped_list_response() -> None:
    fixture = load("sogc_bydate_response.json")
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{SOGC_BASE}/2026-05-15", json={"list": fixture})
        result = fetch_publications_by_date(date(2026, 5, 15))
    assert len(result) == 4


def test_fetch_raises_on_http_error() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{SOGC_BASE}/2026-05-15", status=500)
        with pytest.raises(requests.HTTPError):
            fetch_publications_by_date(date(2026, 5, 15))


# ── filter_new_entries_for_canton ─────────────────────────────────────────────

def test_filter_returns_lu_new_uids() -> None:
    fixture = load("sogc_bydate_response.json")
    uids = filter_new_entries_for_canton(fixture, "LU")
    assert set(uids) == {"CHE319270603", "CHE144292498"}


def test_filter_excludes_wrong_canton() -> None:
    # CHE999999901 is in BE, not LU
    fixture = load("sogc_bydate_response.json")
    uids = filter_new_entries_for_canton(fixture, "LU")
    assert "CHE999999901" not in uids


def test_filter_excludes_non_new_mutation() -> None:
    # CHE888888801 is LU but only has adressaenderung
    fixture = load("sogc_bydate_response.json")
    uids = filter_new_entries_for_canton(fixture, "LU")
    assert "CHE888888801" not in uids


def test_filter_empty_input() -> None:
    assert filter_new_entries_for_canton([], "LU") == []


def test_filter_different_canton_from_same_fixture() -> None:
    fixture = load("sogc_bydate_response.json")
    uids = filter_new_entries_for_canton(fixture, "BE")
    assert uids == ["CHE999999901"]


def test_filter_skips_entry_missing_uid() -> None:
    publications = [
        {
            "sogcPublication": {
                "registryOfCommerceCanton": "LU",
                "mutationTypes": [{"id": 2, "key": "status.neu"}],
            },
            "companyShort": {},  # uid missing
        }
    ]
    assert filter_new_entries_for_canton(publications, "LU") == []


def test_filter_skips_non_list_mutation_types() -> None:
    publications = [
        {
            "sogcPublication": {
                "registryOfCommerceCanton": "LU",
                "mutationTypes": None,  # not a list
            },
            "companyShort": {"uid": "CHE111111111"},
        }
    ]
    assert filter_new_entries_for_canton(publications, "LU") == []
