import time
from collections.abc import Callable

import requests


def call_with_retry[T](
    fn: Callable[[], T],
    max_retries: int = 3,
    _sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call fn(), retrying on Timeout and HTTP 5xx with exponential back-off."""
    for attempt in range(max_retries):
        try:
            return fn()
        except requests.Timeout:
            if attempt < max_retries - 1:
                _sleep(2.0**attempt)
            else:
                raise
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code < 500:
                raise
            if attempt < max_retries - 1:
                _sleep(2.0**attempt)
            else:
                raise
    raise RuntimeError("unreachable")  # satisfies the type checker
