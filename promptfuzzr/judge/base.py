"""Common interface every judge implements."""

from __future__ import annotations

from typing import Protocol

from promptfuzzr.models import TestCase, Verdict


class Judge(Protocol):
    basis: str  # matches models.VerdictBasis

    def evaluate(self, test_case: TestCase) -> tuple[Verdict, float]:
        """Return (verdict, confidence) for an executed TestCase."""
        ...
