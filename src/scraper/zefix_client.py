"""Zefix REST API client – search and detail endpoints.

Rate limiting (sleep between calls) is handled by the caller (pipeline.py),
not here. Each function makes exactly one HTTP request.
"""

from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from common.config import get_settings
from common.http import call_with_retry


def _auth() -> HTTPBasicAuth:
    s = get_settings()
    return HTTPBasicAuth(s.zefix_username, s.zefix_password)


def _json_headers() -> dict[str, str]:
    return {"Accept": "application/json", "Content-Type": "application/json"}


def _post_search(payload: dict[str, Any], timeout: int = 30) -> list[dict[str, Any]]:
    def _call() -> list[dict[str, Any]]:
        s = get_settings()
        resp = requests.post(
            f"{s.zefix_base_url}/company/search",
            auth=_auth(),
            headers=_json_headers(),
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data: Any = resp.json()
        return data if isinstance(data, list) else data.get("list", [])
    return call_with_retry(_call)


def search_by_name_prefix(
    prefix: str,
    canton: str,
    active_only: bool,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """POST /company/search with name='{prefix}*'. Used by the backfill pipeline."""
    return _post_search(
        {"name": f"{prefix}*", "canton": canton, "activeOnly": active_only},
        timeout=timeout,
    )


def search_by_uid(
    uid: str,
    canton: str,
    active_only: bool,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """POST /company/search with name=uid (no wildcard). Used by the daily sync."""
    return _post_search(
        {"name": uid, "canton": canton, "activeOnly": active_only},
        timeout=timeout,
    )


def fetch_detail(uid: str, timeout: int = 30) -> list[dict[str, Any]]:
    """GET /company/uid/{uid}. Wraps a single-dict response in a list."""
    def _call() -> list[dict[str, Any]]:
        s = get_settings()
        resp = requests.get(
            f"{s.zefix_base_url}/company/uid/{uid}",
            auth=_auth(),
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data: Any = resp.json()
        return data if isinstance(data, list) else [data]
    return call_with_retry(_call)
