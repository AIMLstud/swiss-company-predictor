"""SOGC (Swiss Official Gazette of Commerce) client.

fetch_publications_by_date  – GET /sogc/bydate/{date}, returns CH-wide publications.
filter_new_entries_for_canton – pure function; no I/O.
"""

from datetime import date
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from common.config import get_settings
from common.http import call_with_retry


def fetch_publications_by_date(d: date, timeout: int = 30) -> list[dict[str, Any]]:
    """GET /sogc/bydate/{date} – all SOGC publications for that date (CH-wide)."""
    def _call() -> list[dict[str, Any]]:
        s = get_settings()
        resp = requests.get(
            f"{s.zefix_base_url}/sogc/bydate/{d.isoformat()}",
            auth=HTTPBasicAuth(s.zefix_username, s.zefix_password),
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data: Any = resp.json()
        return data if isinstance(data, list) else data.get("list", [])
    return call_with_retry(_call)


def filter_new_entries_for_canton(
    publications: list[dict[str, Any]], canton: str
) -> list[str]:
    """Return UIDs of publications that are new registrations (status.neu) in canton."""
    uids: list[str] = []
    for pub in publications:
        sogc = pub.get("sogcPublication", {})
        if sogc.get("registryOfCommerceCanton") != canton:
            continue
        mt = sogc.get("mutationTypes", [])
        if not isinstance(mt, list):
            continue
        if not any(m.get("key") == "status.neu" for m in mt):
            continue
        uid = pub.get("companyShort", {}).get("uid")
        if uid:
            uids.append(str(uid))
    return uids
