"""Retry policy implementation. See roadmap.md non-determinism note:
retry failed payloads 5-10x before marking fail, log retry_count per
case rather than silently averaging it away.

This retries based on OUTCOME, not just exceptions — a clean refusal
response (no exception, just "I can't help with that") is exactly the
non-determinism case the roadmap note is about: the same payload might
succeed on attempt 4 even though attempts 1-3 failed cleanly. An
exception (network error, malformed response) also triggers a retry,
since both are "this attempt didn't produce a usable result."
"""

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
    """Call fn() up to policy.max_retries times. Stops early and
    returns as soon as fn() succeeds AND should_retry(result) is
    False (e.g. the judge found a SUCCESS verdict). If every attempt
    either raises or keeps should_retry() True, returns the LAST
    result/exception rather than the first — so a caller inspecting
    the return always sees the most-recent attempt, matching how a
    human re-running a flaky test would report the final state.

    Returns (result, attempts_used) so the caller can record
    retry_count = attempts_used - 1.
    """
    last_result: T | None = None
    last_exc: Exception | None = None

    for attempt in range(1, policy.max_retries + 1):
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any failure is retryable here
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

    return last_result, policy.max_retries  # type: ignore[return-value]
