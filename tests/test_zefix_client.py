import json
from pathlib import Path

import pytest
import requests
import responses as rsps_lib

from scraper.zefix_client import fetch_detail, search_by_name_prefix, search_by_uid

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_URL = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search"
DETAIL_BASE = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/uid"


def load(name: str) -> list[dict]:  # type: ignore[type-arg]
    return json.loads((FIXTURES / name).read_text())  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def zefix_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ZEFIX_USERNAME", "testuser")
    monkeypatch.setenv("ZEFIX_PASSWORD", "testpass")
    monkeypatch.setenv("ZEFIX_BASE_URL", "https://www.zefix.admin.ch/ZefixPublicREST/api/v1")


# ── search_by_name_prefix ─────────────────────────────────────────────────────


def test_search_by_prefix_returns_results() -> None:
    fixture = load("zefix_search_response.json")
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, json=fixture)
        result = search_by_name_prefix("a", "LU", active_only=True)
    assert len(result) == 2
    assert result[0]["uid"] == "CHE107251578"
    assert result[1]["uid"] == "CHE338108860"


def test_search_by_prefix_sends_wildcard_payload() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, json=[])
        search_by_name_prefix("b", "LU", active_only=True)
        payload = json.loads(rsps.calls[0].request.body)
    assert payload["name"] == "b*"
    assert payload["canton"] == "LU"
    assert payload["activeOnly"] is True


def test_search_by_prefix_active_only_false() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, json=[])
        search_by_name_prefix("x", "LU", active_only=False)
        payload = json.loads(rsps.calls[0].request.body)
    assert payload["activeOnly"] is False


def test_search_handles_wrapped_list_response() -> None:
    """API may return {"list": [...], "total": N} instead of a bare list."""
    fixture = load("zefix_search_response.json")
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, json={"list": fixture, "total": 2})
        result = search_by_name_prefix("a", "LU", active_only=True)
    assert len(result) == 2


def test_search_raises_on_http_error() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, status=503)
        with pytest.raises(requests.HTTPError):
            search_by_name_prefix("a", "LU", active_only=True)


# ── search_by_uid ─────────────────────────────────────────────────────────────


def test_search_by_uid_sends_uid_without_wildcard() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, json=[])
        search_by_uid("CHE107251578", "LU", active_only=False)
        payload = json.loads(rsps.calls[0].request.body)
    assert payload["name"] == "CHE107251578"
    assert "*" not in payload["name"]
    assert payload["activeOnly"] is False


def test_search_by_uid_returns_results() -> None:
    fixture = load("zefix_search_response.json")[:1]
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.POST, SEARCH_URL, json=fixture)
        result = search_by_uid("CHE107251578", "LU", active_only=False)
    assert result[0]["uid"] == "CHE107251578"


# ── fetch_detail ──────────────────────────────────────────────────────────────


def test_fetch_detail_returns_list() -> None:
    fixture = load("zefix_detail_response.json")
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{DETAIL_BASE}/CHE107251578", json=fixture)
        result = fetch_detail("CHE107251578")
    assert isinstance(result, list)
    assert result[0]["cantonalExcerptWeb"] == (
        "https://lu.chregister.ch/cr-portal/auszug/auszug.xhtml?uid=CHE-107.251.578"
    )


def test_fetch_detail_wraps_single_dict_response() -> None:
    """API may return a single dict instead of a list."""
    single = load("zefix_detail_response.json")[0]
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{DETAIL_BASE}/CHE107251578", json=single)
        result = fetch_detail("CHE107251578")
    assert isinstance(result, list)
    assert len(result) == 1


def test_fetch_detail_raises_on_http_error() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, f"{DETAIL_BASE}/CHE000000000", status=404)
        with pytest.raises(requests.HTTPError):
            fetch_detail("CHE000000000")
