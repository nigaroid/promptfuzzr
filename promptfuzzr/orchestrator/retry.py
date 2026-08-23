from __future__ import annotations

import time
from typing import Callable, TypeVar

from promptfuzzr.config import RetryPolicy

T = TypeVar("T")


def retry_with_policy(
    fn: Callable[[], T],
    policy: RetryPolicy,
    should_retry: Callable[[T], bool] = lambda _result: False,
) -> tuple[T, int]:
    last_result: T | None = None
    last_exc: Exception | None = None

    for attempt in range(1, policy.max_retries + 1):
        try:
            result = fn()
        except Exception as exc:
            last_exc = exc
            if attempt == policy.max_retries:
                raise
            time.sleep(policy.backoff_seconds)
            continue

        last_result = result
        last_exc = None

        if not should_retry(result):
            return result, attempt

        if attempt < policy.max_retries:
            time.sleep(policy.backoff_seconds)

    return last_result, policy.max_retries
