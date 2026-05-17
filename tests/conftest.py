"""
Session-scoped HTTP guard: blocks every real network call for the entire test run.

Tests that need HTTP responses use the `responses` library, which intercepts at
requests.adapters.HTTPAdapter.send (above urllib3) and is unaffected by this patch.
Any call that bypasses `responses` and reaches urllib3 triggers RuntimeError.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True, scope="session")
def block_real_http() -> None:
    with patch(
        "urllib3.HTTPConnectionPool.urlopen",
        side_effect=RuntimeError(
            "Real HTTP call blocked in test suite. "
            "Use the `responses` library to register mock responses."
        ),
    ):
        yield
