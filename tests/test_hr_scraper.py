from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import pytest
import requests
import responses as rsps_lib

from scraper.hr_scraper import (
    ViewStateMissingError,
    _parse_eintragsdatum,
    scrape_eintragsdatum_from_url,
    scrape_with_retry,
)

FIXTURES = Path(__file__).parent / "fixtures"
HR_URL = "https://lu.chregister.ch/cr-portal/auszug/auszug.xhtml?uid=CHE-107.251.578"


def html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ── _parse_eintragsdatum (unit, no HTTP) ──────────────────────────────────────


def test_parse_regex_match() -> None:
    text = "<span>Eingetragen am</span><span>07.09.1998</span>"
    assert _parse_eintragsdatum(text) == date(1998, 9, 7)


def test_parse_regex_with_whitespace_between_spans() -> None:
    text = "<span>Eingetragen am</span>  \n  <span>01.01.2020</span>"
    assert _parse_eintragsdatum(text) == date(2020, 1, 1)


def test_parse_soup_fallback() -> None:
    # No </span><span> structure – only plain text; must use BeautifulSoup fallback
    text = "<td>Eingetragen am: 07.09.1998</td>"
    assert _parse_eintragsdatum(text) == date(1998, 9, 7)


def test_parse_returns_none_when_no_date() -> None:
    assert _parse_eintragsdatum("<html>No date here</html>") is None


# ── scrape_eintragsdatum_from_url ──────────────────────────────────────────────


def test_scrape_returns_date() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, body=html("hr_auszug_page.html"))
        rsps.add(rsps_lib.POST, HR_URL, body=html("hr_auszug_ajax.html"))
        result = scrape_eintragsdatum_from_url(HR_URL)
    assert result == date(1998, 9, 7)


def test_scrape_sends_viewstate_in_post() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, body=html("hr_auszug_page.html"))
        rsps.add(rsps_lib.POST, HR_URL, body=html("hr_auszug_ajax.html"))
        scrape_eintragsdatum_from_url(HR_URL)
        post_body = rsps.calls[1].request.body
    assert post_body is not None
    params = parse_qs(post_body if isinstance(post_body, str) else post_body.decode())
    assert params["javax.faces.ViewState"] == ["test-view-state-xyz"]


def test_scrape_raises_viewstate_missing() -> None:
    page_no_vs = "<html><body><form id='idAuszugForm'></form></body></html>"
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, body=page_no_vs)
        with pytest.raises(ViewStateMissingError):
            scrape_eintragsdatum_from_url(HR_URL)


def test_scrape_returns_none_when_date_not_in_ajax() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, body=html("hr_auszug_page.html"))
        rsps.add(
            rsps_lib.POST, HR_URL, body="<partial-response><changes></changes></partial-response>"
        )
        result = scrape_eintragsdatum_from_url(HR_URL)
    assert result is None


def test_scrape_raises_on_get_http_error() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, status=403)
        with pytest.raises(requests.HTTPError):
            scrape_eintragsdatum_from_url(HR_URL)


def test_scrape_raises_on_post_http_error() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, body=html("hr_auszug_page.html"))
        rsps.add(rsps_lib.POST, HR_URL, status=500)
        with pytest.raises(requests.HTTPError):
            scrape_eintragsdatum_from_url(HR_URL)


def test_scrape_returns_none_for_empty_url() -> None:
    assert scrape_eintragsdatum_from_url("") is None


# ── scrape_with_retry ─────────────────────────────────────────────────────────


def test_retry_succeeds_after_one_timeout() -> None:
    sleep_calls: list[float] = []

    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, body=requests.exceptions.Timeout())
        rsps.add(rsps_lib.GET, HR_URL, body=html("hr_auszug_page.html"))
        rsps.add(rsps_lib.POST, HR_URL, body=html("hr_auszug_ajax.html"))
        result = scrape_with_retry(HR_URL, max_retries=3, _sleep=sleep_calls.append)

    assert result == date(1998, 9, 7)
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 1.0  # 2^0


def test_retry_raises_after_max_retries_exceeded() -> None:
    with rsps_lib.RequestsMock() as rsps:
        for _ in range(3):
            rsps.add(rsps_lib.GET, HR_URL, body=requests.exceptions.Timeout())
        with pytest.raises(requests.Timeout):
            scrape_with_retry(HR_URL, max_retries=3, _sleep=lambda _: None)


def test_retry_no_retry_on_4xx() -> None:
    sleep_calls: list[float] = []

    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, status=404)
        with pytest.raises(requests.HTTPError):
            scrape_with_retry(HR_URL, max_retries=3, _sleep=sleep_calls.append)

    assert sleep_calls == []  # no retries for 4xx


def test_retry_retries_on_5xx() -> None:
    with rsps_lib.RequestsMock() as rsps:
        rsps.add(rsps_lib.GET, HR_URL, status=503)
        rsps.add(rsps_lib.GET, HR_URL, body=html("hr_auszug_page.html"))
        rsps.add(rsps_lib.POST, HR_URL, body=html("hr_auszug_ajax.html"))
        result = scrape_with_retry(HR_URL, max_retries=3, _sleep=lambda _: None)

    assert result == date(1998, 9, 7)
