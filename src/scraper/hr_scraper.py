"""HR-Auszug scraper (lu.chregister.ch).

Two-step flow per URL:
  1. GET page  → extract javax.faces.ViewState
  2. POST AJAX → load lazy content panel, extract "Eingetragen am" date

scrape_eintragsdatum_from_url – single attempt, raises on HTTP / missing ViewState
scrape_with_retry             – wraps above with exponential back-off for transient errors
"""

import re
import time
from collections.abc import Callable
from datetime import date, datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class ViewStateMissingError(Exception):
    """Raised when javax.faces.ViewState is not found in the page HTML."""


_DATE_RE = re.compile(
    r"Eingetragen am</span>\s*<span>(\d{2}\.\d{2}\.\d{4})</span>"
)

_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "de-CH,de;q=0.9",
}


def _parse_eintragsdatum(text: str) -> date | None:
    """Regex-first, BeautifulSoup plain-text fallback."""
    m = _DATE_RE.search(text)
    if m:
        return datetime.strptime(m.group(1), "%d.%m.%Y").date()
    soup = BeautifulSoup(text, "html.parser")
    plain = soup.get_text(" ", strip=True)
    m2 = re.search(
        r"Eingetragen\s+am[\s:]*(\d{2}\.\d{2}\.\d{4})",
        plain,
        flags=re.IGNORECASE,
    )
    return datetime.strptime(m2.group(1), "%d.%m.%Y").date() if m2 else None


def scrape_eintragsdatum_from_url(
    url: str,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> date | None:
    """Scrape the Eingetragen-am date from an HR-Auszug URL.

    Returns:
        date: found and parsed successfully
        None: page loaded but "Eingetragen am" not found

    Raises:
        ViewStateMissingError: ViewState input absent in the page HTML
        requests.HTTPError: non-2xx HTTP response
        requests.Timeout: request timed out
    """
    if not url or not isinstance(url, str):
        return None

    sess = session if session is not None else requests.Session()
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.hostname}"

    # Step 1 – load page, grab ViewState
    r1 = sess.get(url, headers=_BROWSER_HEADERS, timeout=timeout)
    r1.raise_for_status()

    soup = BeautifulSoup(r1.text, "html.parser")
    vs_el = soup.find("input", {"name": "javax.faces.ViewState"})
    if not vs_el:
        raise ViewStateMissingError(f"No ViewState found at {url!r}")
    view_state: str = str(vs_el.get("value", ""))

    # Step 2 – AJAX postback to render lazy content panel
    ajax_headers: dict[str, str] = {
        **_BROWSER_HEADERS,
        "Faces-Request": "partial/ajax",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": origin,
        "Referer": r1.url,
    }
    post_data = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "idAuszugForm:auszugContentPanel",
        "javax.faces.partial.execute": "idAuszugForm:auszugContentPanel",
        "javax.faces.partial.render": "idAuszugForm:auszugContentPanel",
        "idAuszugForm:auszugContentPanel_load": "true",
        "idAuszugForm": "idAuszugForm",
        "javax.faces.ViewState": view_state,
    }
    r2 = sess.post(url, data=post_data, headers=ajax_headers, timeout=timeout)
    r2.raise_for_status()

    return _parse_eintragsdatum(r2.text)


def scrape_with_retry(
    url: str,
    session: requests.Session | None = None,
    max_retries: int = 3,
    timeout: int = 30,
    _sleep: Callable[[float], None] = time.sleep,
) -> date | None:
    """scrape_eintragsdatum_from_url with exponential back-off.

    Retries on requests.Timeout and HTTP 5xx. Raises immediately on 4xx.
    """
    for attempt in range(max_retries):
        try:
            return scrape_eintragsdatum_from_url(url, session=session, timeout=timeout)
        except requests.Timeout:
            if attempt < max_retries - 1:
                _sleep(2.0**attempt)
            else:
                raise
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code < 500:
                raise  # 4xx is not transient
            if attempt < max_retries - 1:
                _sleep(2.0**attempt)
            else:
                raise
    return None  # unreachable; satisfies the type checker
