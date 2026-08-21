"""ddmin-style (delta-debugging) reduction of a successful TestCase
payload. Given a payload that triggered a SUCCESS verdict, binary-
search-remove chunks (sentence/token/char granularity depending on
encoding) and re-verify against the target after each cut, keeping
only cuts that preserve the success verdict.

This is a real differentiator per roadmap.md section 0 — budget actual
implementation time for it in Phase 5, not a stretch goal.

TODO(phase 5):
  1. chunk_payload(payload, granularity) -> list[str]
  2. ddmin(chunks, verify_fn) -> list[str]   # classic delta-debugging loop
  3. minimize_test_case(test_case, target, judge) -> str  # orchestrates
     re-running the (possibly reduced) payload against the same target/
     session config and checking the verdict is still SUCCESS
"""

from __future__ import annotations

from typing import Callable

from promptfuzzr.models import TestCase


def chunk_payload(payload: str, granularity: str = "sentence") -> list[str]:
    raise NotImplementedError("TODO(phase 5): split payload into reducible chunks")


def ddmin(chunks: list[str], verify_fn: Callable[[list[str]], bool]) -> list[str]:
    """Classic delta-debugging minimization loop.
    verify_fn(candidate_chunks) -> True if the exploit still succeeds
    with only those chunks present.
    """
    raise NotImplementedError("TODO(phase 5): implement the ddmin reduction loop")


def minimize_test_case(test_case: TestCase, target, judge) -> str:
    """Full pipeline: chunk -> ddmin -> re-verify -> return minimal
    payload string. Also sets test_case.minimized_payload as a side
    effect for convenience when called from the CLI.
    """
    raise NotImplementedError("TODO(phase 5): orchestrate chunk_payload + ddmin against target/judge")
